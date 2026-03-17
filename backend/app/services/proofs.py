from __future__ import annotations

import base64
import hashlib
import json
import secrets
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from ..models import ExternalVerificationSession


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _urlsafe_token(length: int = 24) -> str:
    return secrets.token_urlsafe(length)


def _sha256_urlsafe(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


def _base58_decode(value: str) -> bytes:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number = 0
    for char in value:
        number = number * 58 + alphabet.index(char)
    combined = number.to_bytes((number.bit_length() + 7) // 8, byteorder="big") if number else b""
    leading_zero_count = len(value) - len(value.lstrip("1"))
    return b"\x00" * leading_zero_count + combined


def create_wallet_verification_session(agent, chain: str, address: str) -> ExternalVerificationSession:
    state = _urlsafe_token(18)
    issued_at = utcnow()
    payload = {
        "agent_id": agent.id,
        "agent_handle": agent.handle,
        "chain": chain,
        "address": address,
        "issued_at": issued_at.isoformat(),
        "expires_at": (issued_at + timedelta(minutes=10)).isoformat(),
        "nonce": state,
        "purpose": "wallet_verification",
    }
    return ExternalVerificationSession(
        agent_id=agent.id,
        provider=chain,
        session_kind="wallet",
        state=state,
        challenge_payload=payload,
        expires_at=issued_at + timedelta(minutes=10),
    )


def wallet_message_from_payload(payload: dict) -> str:
    return "\n".join(
        [
            "AgentLayer wallet verification",
            f"agent_id: {payload['agent_id']}",
            f"agent_handle: {payload['agent_handle']}",
            f"chain: {payload['chain']}",
            f"address: {payload['address']}",
            f"nonce: {payload['nonce']}",
            f"issued_at: {payload['issued_at']}",
            f"expires_at: {payload['expires_at']}",
        ]
    )


def verify_evm_wallet_signature(message: str, signature_hex: str, expected_address: str) -> bool:
    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct
    except ModuleNotFoundError as exc:
        raise RuntimeError("eth-account is not installed. Run `pip install -r requirements.txt`.") from exc
    signature = signature_hex if signature_hex.startswith("0x") else f"0x{signature_hex}"
    recovered = Account.recover_message(encode_defunct(text=message), signature=signature)
    return recovered.lower() == expected_address.lower()


def verify_solana_wallet_signature(message: str, signature_b64: str, expected_address: str) -> bool:
    try:
        from nacl.signing import VerifyKey
    except ModuleNotFoundError as exc:
        raise RuntimeError("PyNaCl is not installed. Run `pip install -r requirements.txt`.") from exc
    verify_key = VerifyKey(_base58_decode(expected_address))
    signature = base64.b64decode(signature_b64)
    verify_key.verify(message.encode("utf-8"), signature)
    return True


def create_oauth_session(agent, provider: str) -> ExternalVerificationSession:
    state = _urlsafe_token(24)
    code_verifier = _urlsafe_token(48)
    return ExternalVerificationSession(
        agent_id=agent.id,
        provider=provider,
        session_kind="oauth",
        state=state,
        code_verifier=code_verifier,
        challenge_payload={"agent_id": agent.id, "provider": provider},
        expires_at=utcnow() + timedelta(minutes=15),
    )


def github_authorize_url(client_id: str, redirect_uri: str, session: ExternalVerificationSession) -> str:
    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "read:user user:email",
            "state": session.state,
        }
    )
    return f"https://github.com/login/oauth/authorize?{query}"


def x_authorize_url(client_id: str, redirect_uri: str, session: ExternalVerificationSession) -> str:
    query = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "tweet.read users.read offline.access",
            "state": session.state,
            "code_challenge": _sha256_urlsafe(session.code_verifier or ""),
            "code_challenge_method": "S256",
        }
    )
    return f"https://x.com/i/oauth2/authorize?{query}"


def _request_json(
    url: str,
    *,
    method: str = "GET",
    data: dict | None = None,
    headers: dict[str, str] | None = None,
) -> dict:
    payload = None
    request_headers = headers.copy() if headers else {}
    if data is not None:
        payload = urllib.parse.urlencode(data).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    request_headers.setdefault("Accept", "application/json")
    request = urllib.request.Request(url, data=payload, headers=request_headers, method=method)
    with urllib.request.urlopen(request) as response:
        body = response.read().decode("utf-8")
        return json.loads(body)


def exchange_github_code(code: str, *, client_id: str, client_secret: str, redirect_uri: str) -> dict:
    token = _request_json(
        "https://github.com/login/oauth/access_token",
        method="POST",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        },
    )
    user = _request_json(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {token['access_token']}"},
    )
    return {
        "login": user.get("login"),
        "profile_url": user.get("html_url"),
        "id": user.get("id"),
    }


def exchange_x_code(
    code: str,
    *,
    client_id: str,
    client_secret: str | None,
    redirect_uri: str,
    code_verifier: str,
) -> dict:
    headers = {}
    if client_secret:
        basic = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("utf-8")
        headers["Authorization"] = f"Basic {basic}"
    token_payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
        "client_id": client_id,
    }
    token = _request_json(
        "https://api.x.com/2/oauth2/token",
        method="POST",
        data=token_payload,
        headers=headers,
    )
    user = _request_json(
        "https://api.x.com/2/users/me?user.fields=username,name",
        headers={"Authorization": f"Bearer {token['access_token']}"},
    )
    data = user.get("data", {})
    return {
        "username": data.get("username"),
        "name": data.get("name"),
        "id": data.get("id"),
        "profile_url": f"https://x.com/{data.get('username')}" if data.get("username") else None,
    }
