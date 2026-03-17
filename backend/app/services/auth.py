from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .crypto import sign_platform_payload, verify_platform_signature


def create_agent_auth_challenge(platform_signing_key, agent_id: str, ttl_minutes: int = 5) -> dict:
    issued_at = datetime.now(timezone.utc)
    payload = {
        "challenge_id": str(uuid4()),
        "agent_id": agent_id,
        "nonce": str(uuid4()),
        "issued_at": issued_at.isoformat(),
        "expires_at": (issued_at + timedelta(minutes=ttl_minutes)).isoformat(),
        "purpose": "agent_authentication",
    }
    return {
        "payload": payload,
        "platform_signature": sign_platform_payload(platform_signing_key, payload),
        "platform_signature_algorithm": "Ed25519",
    }


def verify_signed_platform_payload(public_key_pem: str, payload: dict, signature: str) -> bool:
    return verify_platform_signature(public_key_pem, payload, signature)


def create_auth_proof(platform_signing_key, agent, ttl_minutes: int = 15) -> dict:
    issued_at = datetime.now(timezone.utc)
    payload = {
        "proof_id": str(uuid4()),
        "agent_id": agent.id,
        "issued_at": issued_at.isoformat(),
        "expires_at": (issued_at + timedelta(minutes=ttl_minutes)).isoformat(),
        "trust_score": round(float(agent.trust_score), 2),
        "purpose": "agent_runtime_auth",
    }
    return {
        "payload": payload,
        "platform_signature": sign_platform_payload(platform_signing_key, payload),
        "platform_signature_algorithm": "Ed25519",
    }


def allowed_scopes_for_tier(access_tier: str) -> list[str]:
    scopes = {
        "profile:read",
        "profile:write",
        "proof:write",
        "passport:read",
        "attest:write",
        "release:write",
        "release:verify",
        "bond:write",
        "dispute:write",
    }
    if access_tier in {"network", "marketplace", "settlement"}:
        scopes.add("directory:priority")
    if access_tier in {"marketplace", "settlement"}:
        scopes.update({"marketplace:access", "reputation:export", "holdback:write", "review:write"})
    if access_tier == "settlement":
        scopes.update({"settlement:access", "slash:write"})
    return sorted(scopes)


def normalize_requested_scopes(access_tier: str, requested_scopes: list[str] | None) -> list[str]:
    allowed = set(allowed_scopes_for_tier(access_tier))
    if not requested_scopes:
        return sorted(allowed)
    return sorted(scope for scope in requested_scopes if scope in allowed)


def create_session_tokens(
    platform_signing_key,
    agent,
    *,
    session_id: str,
    refresh_token_id: str,
    partner: str | None,
    scopes: list[str],
    access_ttl_minutes: int = 15,
    refresh_ttl_days: int = 14,
) -> dict:
    issued_at = datetime.now(timezone.utc)
    access_payload = {
        "token_id": str(uuid4()),
        "session_id": session_id,
        "agent_id": agent.id,
        "kind": "access",
        "partner": partner,
        "scopes": scopes,
        "issued_at": issued_at.isoformat(),
        "expires_at": (issued_at + timedelta(minutes=access_ttl_minutes)).isoformat(),
        "purpose": "agent_runtime_access",
    }
    refresh_payload = {
        "token_id": refresh_token_id,
        "session_id": session_id,
        "agent_id": agent.id,
        "kind": "refresh",
        "partner": partner,
        "scopes": scopes,
        "issued_at": issued_at.isoformat(),
        "expires_at": (issued_at + timedelta(days=refresh_ttl_days)).isoformat(),
        "purpose": "agent_runtime_refresh",
    }
    return {
        "access_token": {
            "payload": access_payload,
            "platform_signature": sign_platform_payload(platform_signing_key, access_payload),
            "platform_signature_algorithm": "Ed25519",
        },
        "refresh_token": {
            "payload": refresh_payload,
            "platform_signature": sign_platform_payload(platform_signing_key, refresh_payload),
            "platform_signature_algorithm": "Ed25519",
        },
    }


def auth_proof_is_valid(platform_public_key_pem: str, auth_proof: dict, agent_id: str) -> bool:
    payload = auth_proof.get("payload")
    signature = auth_proof.get("platform_signature")
    if not payload or not signature:
        return False
    if payload.get("agent_id") != agent_id:
        return False
    try:
        expires_at = datetime.fromisoformat(payload["expires_at"].replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return False
    if datetime.now(timezone.utc) > expires_at:
        return False
    return verify_signed_platform_payload(platform_public_key_pem, payload, signature)


def session_token_is_valid(
    platform_public_key_pem: str,
    token: dict,
    *,
    agent_id: str,
    expected_kind: str,
    required_scope: str | None = None,
    session=None,
) -> bool:
    payload = token.get("payload")
    signature = token.get("platform_signature")
    if not payload or not signature:
        return False
    if payload.get("agent_id") != agent_id:
        return False
    if payload.get("kind") != expected_kind:
        return False
    try:
        expires_at = datetime.fromisoformat(payload["expires_at"].replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return False
    if datetime.now(timezone.utc) > expires_at:
        return False
    if required_scope and required_scope not in payload.get("scopes", []):
        return False
    if session is not None:
        if session.id != payload.get("session_id"):
            return False
        if session.revoked_at is not None:
            return False
        if session.refresh_token_id != payload.get("token_id") and expected_kind == "refresh":
            return False
    return verify_signed_platform_payload(platform_public_key_pem, payload, signature)


def new_session_ids() -> tuple[str, str]:
    return str(uuid4()), str(uuid4())
