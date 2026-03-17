from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat


def canonical_json(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def sign_claim(private_key: ec.EllipticCurvePrivateKey, payload: dict) -> str:
    signature = private_key.sign(canonical_json(payload), ec.ECDSA(hashes.SHA256()))
    return base64.b64encode(signature).decode("utf-8")


def load_private_key(path: Path) -> ec.EllipticCurvePrivateKey:
    return serialization.load_pem_private_key(path.read_bytes(), password=None)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def private_key_to_pem(private_key: ec.EllipticCurvePrivateKey) -> str:
    return private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode("utf-8")


def public_key_to_pem(private_key: ec.EllipticCurvePrivateKey) -> str:
    return private_key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode("utf-8")


def fingerprint_public_key_pem(public_key_pem: str) -> str:
    return f"sha256:{hashlib.sha256(public_key_pem.encode('utf-8')).hexdigest()}"


def fetch_json(url: str, method: str = "GET", payload: dict | None = None) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        raise SystemExit(f"{method} {url} failed: {exc.code} {body}") from exc


def generate_identity(workspace: Path) -> tuple[Path, Path]:
    workspace.mkdir(parents=True, exist_ok=True)
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_key_path = workspace / "private_key.pem"
    public_key_path = workspace / "public_key.pem"

    private_key_path.write_bytes(
        private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    )
    public_key_path.write_bytes(
        private_key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
    )
    return private_key_path, public_key_path


def import_existing_private_key(workspace: Path, source: Path) -> tuple[Path, Path]:
    workspace.mkdir(parents=True, exist_ok=True)
    private_key = load_private_key(source)
    private_key_path = workspace / "private_key.pem"
    public_key_path = workspace / "public_key.pem"
    private_key_path.write_bytes(
        private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    )
    public_key_path.write_bytes(
        private_key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
    )
    return private_key_path, public_key_path


def registration_challenge(platform_url: str) -> dict:
    return fetch_json(f"{platform_url.rstrip('/')}/api/v1/registration/challenge", method="POST", payload={})


def auth_challenge(platform_url: str, agent_id: str) -> dict:
    return fetch_json(
        f"{platform_url.rstrip('/')}/api/v1/auth/challenge",
        method="POST",
        payload={"agent_id": agent_id},
    )


def workspace_paths(workspace: Path) -> dict[str, Path]:
    return {
        "private_key": workspace / "private_key.pem",
        "public_key": workspace / "public_key.pem",
        "identity": workspace / "identity.json",
        "agent": workspace / "agent.json",
        "passport": workspace / "passport.json",
        "auth_proof": workspace / "auth_proof.json",
        "session": workspace / "session.json",
        "releases": workspace / "releases.json",
        "economic": workspace / "economic_security.json",
        "recovery_keys": workspace / "recovery_keys.json",
    }


def load_workspace(workspace: Path) -> dict:
    paths = workspace_paths(workspace)
    if not paths["agent"].exists():
        raise SystemExit("Missing agent.json. Run init first.")
    return load_json(paths["agent"])


def register_agent(
    workspace: Path,
    platform_url: str,
    name: str,
    description: str,
    homepage_url: str | None,
    capabilities: list[str],
    tags: list[str],
    moltbook_identity_token: str | None = None,
    recovery_public_keys: list[dict] | None = None,
) -> dict:
    paths = workspace_paths(workspace)
    private_key_path = paths["private_key"]
    public_key_path = paths["public_key"]
    if not private_key_path.exists() or not public_key_path.exists():
        raise SystemExit("Missing local key files. Run init with a generated or imported key first.")

    private_key = load_private_key(private_key_path)
    challenge = registration_challenge(platform_url)
    claim = {
        "name": name,
        "description": description,
        "homepage_url": homepage_url or "",
        "capabilities": capabilities,
        "tags": tags,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "challenge_nonce": challenge["payload"]["nonce"],
        "nonce": challenge["payload"]["challenge_id"],
    }
    signature = sign_claim(private_key, claim)

    response = fetch_json(
        f"{platform_url.rstrip('/')}/api/v1/agents/register",
        method="POST",
        payload={
            "name": name,
            "description": description,
            "homepage_url": homepage_url or "",
            "public_key_pem": public_key_path.read_text(encoding="utf-8"),
            "key_algorithm": "ECDSA_P256_SHA256",
            "signature": signature,
            "recovery_public_keys": recovery_public_keys or [],
            **({"moltbook_identity_token": moltbook_identity_token} if moltbook_identity_token else {}),
            "registration_claim": claim,
            "challenge": {
                "payload": challenge["payload"],
                "platform_signature": challenge["platform_signature"],
            },
        },
    )

    passport_path = paths["passport"]
    agent_path = paths["agent"]
    identity_path = paths["identity"]
    dump_json(passport_path, response["passport"])
    dump_json(
        identity_path,
        {
            "agentId": response["agent"]["id"],
            "name": response["agent"]["name"],
            "privateKeyPem": private_key_path.read_text(encoding="utf-8"),
            "publicKeyPem": public_key_path.read_text(encoding="utf-8"),
        },
    )
    dump_json(
        agent_path,
        {
            "platform_url": platform_url.rstrip("/"),
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "agent": response["agent"],
            "eligibility": response["eligibility"],
            "private_key_path": str(private_key_path.resolve()),
            "public_key_path": str(public_key_path.resolve()),
            "identity_path": str(identity_path.resolve()),
            "passport_path": str(passport_path.resolve()),
            "recovery_public_keys": recovery_public_keys or [],
        },
    )
    return response


def authenticate_agent(workspace: Path, platform_url: str | None = None) -> dict:
    return authenticate_agent_with_scopes(workspace, platform_url, None, None)


def authenticate_agent_with_scopes(
    workspace: Path,
    platform_url: str | None = None,
    requested_scopes: list[str] | None = None,
    partner: str | None = None,
) -> dict:
    paths = workspace_paths(workspace)
    metadata = load_workspace(workspace)
    agent = metadata.get("agent", {})
    resolved_platform = (platform_url or metadata.get("platform_url") or "").rstrip("/")
    if not resolved_platform:
        raise SystemExit("platform_url is missing. Supply --platform or re-run init.")

    private_key = load_private_key(paths["private_key"])
    challenge = auth_challenge(resolved_platform, agent["id"])
    claim = {
        "agent_id": agent["id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "challenge_nonce": challenge["payload"]["nonce"],
        "nonce": challenge["payload"]["challenge_id"],
    }
    signature = sign_claim(private_key, claim)
    response = fetch_json(
        f"{resolved_platform}/api/v1/auth/verify",
        method="POST",
        payload={
            "agent_id": agent["id"],
            "auth_claim": claim,
            "signature": signature,
            "challenge": {
                "payload": challenge["payload"],
                "platform_signature": challenge["platform_signature"],
            },
            "requested_scopes": requested_scopes or [],
            "partner": partner,
        },
    )

    dump_json(paths["auth_proof"], response["auth_proof"])
    dump_json(paths["session"], response["session_tokens"])
    metadata["platform_url"] = resolved_platform
    metadata["last_authenticated_at"] = datetime.now(timezone.utc).isoformat()
    metadata["auth_proof_path"] = str(paths["auth_proof"].resolve())
    metadata["session_path"] = str(paths["session"].resolve())
    metadata["agent"] = response["agent"]
    metadata["granted_scopes"] = response.get("granted_scopes", [])
    metadata["partner"] = response.get("partner")
    dump_json(paths["agent"], metadata)
    return response


def refresh_session(workspace: Path, platform_url: str | None = None) -> dict:
    paths = workspace_paths(workspace)
    metadata = load_workspace(workspace)
    resolved_platform = (platform_url or metadata.get("platform_url") or "").rstrip("/")
    if not resolved_platform:
        raise SystemExit("platform_url is missing. Supply --platform or re-run init.")
    if not paths["session"].exists():
        raise SystemExit("Missing session.json. Run auth first.")
    session_tokens = load_json(paths["session"])
    response = fetch_json(
        f"{resolved_platform}/api/v1/auth/refresh",
        method="POST",
        payload={"refresh_token": session_tokens["refresh_token"]},
    )
    dump_json(paths["session"], response["session_tokens"])
    metadata["platform_url"] = resolved_platform
    metadata["last_refreshed_at"] = datetime.now(timezone.utc).isoformat()
    metadata["session_path"] = str(paths["session"].resolve())
    metadata["agent"] = response["agent"]
    dump_json(paths["agent"], metadata)
    return response


def revoke_session(workspace: Path, platform_url: str | None = None) -> dict:
    paths = workspace_paths(workspace)
    metadata = load_workspace(workspace)
    resolved_platform = (platform_url or metadata.get("platform_url") or "").rstrip("/")
    if not resolved_platform:
        raise SystemExit("platform_url is missing. Supply --platform or re-run init.")
    if not paths["session"].exists():
        raise SystemExit("Missing session.json. Run login/auth first.")
    session_tokens = load_json(paths["session"])
    response = fetch_json(
        f"{resolved_platform}/api/v1/auth/revoke",
        method="POST",
        payload={"refresh_token": session_tokens["refresh_token"]},
    )
    paths["session"].unlink(missing_ok=True)
    paths["auth_proof"].unlink(missing_ok=True)
    metadata["last_revoked_at"] = datetime.now(timezone.utc).isoformat()
    metadata.pop("session_path", None)
    metadata.pop("auth_proof_path", None)
    dump_json(paths["agent"], metadata)
    return response


def ensure_access_token(
    workspace: Path,
    platform_url: str | None = None,
    *,
    required_scope: str | None = None,
    partner: str | None = None,
) -> dict:
    paths = workspace_paths(workspace)
    if paths["session"].exists():
        session_tokens = load_json(paths["session"])
        access_payload = session_tokens.get("access_token", {}).get("payload", {})
        scopes = set(access_payload.get("scopes", []))
        partner_matches = partner is None or access_payload.get("partner") == partner
        expires_at = access_payload.get("expires_at")
        if expires_at:
            try:
                expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            except ValueError:
                expiry = None
            if expiry and expiry > datetime.now(timezone.utc) and (required_scope is None or required_scope in scopes) and partner_matches:
                return session_tokens["access_token"]
        refresh_scopes = set(session_tokens.get("refresh_token", {}).get("payload", {}).get("scopes", []))
        if (required_scope is None or required_scope in refresh_scopes) and partner_matches:
            refreshed = refresh_session(workspace, platform_url)
            return refreshed["session_tokens"]["access_token"]
    requested_scopes = [required_scope] if required_scope else None
    auth = authenticate_agent_with_scopes(workspace, platform_url, requested_scopes, partner)
    return auth["session_tokens"]["access_token"]


def resolve_agent_handle(platform_url: str, handle: str) -> dict:
    return fetch_json(f"{platform_url.rstrip('/')}/api/v1/agents/resolve/{handle}", method="GET")


def load_recovery_public_keys(path: Path | None) -> list[dict]:
    if path is None:
        return []
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise SystemExit(f"Recovery key file not found: {resolved}")
    payload = load_json(resolved)
    if not isinstance(payload, list):
        raise SystemExit("Recovery key file must be a JSON array.")
    return payload


def rotate_agent_key(workspace: Path, platform_url: str | None = None, *, new_private_key_path: Path | None = None) -> dict:
    paths = workspace_paths(workspace)
    metadata = load_workspace(workspace)
    agent = metadata.get("agent", {})
    resolved_platform = (platform_url or metadata.get("platform_url") or "").rstrip("/")
    if not resolved_platform:
        raise SystemExit("platform_url is missing. Supply --platform or re-run init.")

    current_private_key = load_private_key(paths["private_key"])
    if new_private_key_path:
        new_private_key = load_private_key(new_private_key_path.expanduser().resolve())
    else:
        new_private_key = ec.generate_private_key(ec.SECP256R1())

    new_public_key_pem = public_key_to_pem(new_private_key)
    claim = {
        "schema_version": "key_rotation/v1",
        "agent_id": agent["id"],
        "previous_public_key_fingerprint": agent["public_key_fingerprint"],
        "new_public_key_fingerprint": fingerprint_public_key_pem(new_public_key_pem),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "nonce": f"rotate-{datetime.now(timezone.utc).timestamp()}",
    }
    signature = sign_claim(current_private_key, claim)
    response = fetch_json(
        f"{resolved_platform}/api/v1/agents/{agent['id']}/keys/rotate",
        method="POST",
        payload={
            "new_public_key_pem": new_public_key_pem,
            "rotation_claim": claim,
            "signature": signature,
        },
    )
    paths["private_key"].write_text(private_key_to_pem(new_private_key), encoding="utf-8")
    paths["public_key"].write_text(new_public_key_pem, encoding="utf-8")
    dump_json(
        paths["identity"],
        {
            "agentId": response["agent"]["id"],
            "name": response["agent"]["name"],
            "privateKeyPem": private_key_to_pem(new_private_key),
            "publicKeyPem": new_public_key_pem,
        },
    )
    metadata["agent"] = response["agent"]
    metadata["rotated_at"] = datetime.now(timezone.utc).isoformat()
    dump_json(paths["agent"], metadata)
    dump_json(paths["passport"], response["passport"])
    return response


def recover_agent_key(
    workspace: Path,
    platform_url: str | None = None,
    *,
    recovery_private_key_path: Path,
    recovery_key_id: str,
    new_private_key_path: Path | None = None,
) -> dict:
    paths = workspace_paths(workspace)
    metadata = load_workspace(workspace)
    agent = metadata.get("agent", {})
    resolved_platform = (platform_url or metadata.get("platform_url") or "").rstrip("/")
    if not resolved_platform:
        raise SystemExit("platform_url is missing. Supply --platform or re-run init.")

    recovery_private_key = load_private_key(recovery_private_key_path.expanduser().resolve())
    if new_private_key_path:
        new_private_key = load_private_key(new_private_key_path.expanduser().resolve())
    else:
        new_private_key = ec.generate_private_key(ec.SECP256R1())
    new_public_key_pem = public_key_to_pem(new_private_key)
    claim = {
        "schema_version": "key_recovery/v1",
        "agent_id": agent["id"],
        "recovery_key_id": recovery_key_id,
        "new_public_key_fingerprint": fingerprint_public_key_pem(new_public_key_pem),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "nonce": f"recover-{datetime.now(timezone.utc).timestamp()}",
    }
    signature = sign_claim(recovery_private_key, claim)
    response = fetch_json(
        f"{resolved_platform}/api/v1/agents/{agent['id']}/keys/recover",
        method="POST",
        payload={
            "recovery_key_id": recovery_key_id,
            "new_public_key_pem": new_public_key_pem,
            "recovery_claim": claim,
            "signature": signature,
        },
    )
    paths["private_key"].write_text(private_key_to_pem(new_private_key), encoding="utf-8")
    paths["public_key"].write_text(new_public_key_pem, encoding="utf-8")
    dump_json(
        paths["identity"],
        {
            "agentId": response["agent"]["id"],
            "name": response["agent"]["name"],
            "privateKeyPem": private_key_to_pem(new_private_key),
            "publicKeyPem": new_public_key_pem,
        },
    )
    metadata["agent"] = response["agent"]
    metadata["recovered_at"] = datetime.now(timezone.utc).isoformat()
    dump_json(paths["agent"], metadata)
    dump_json(paths["passport"], response["passport"])
    return response


def publish_release(
    workspace: Path,
    platform_url: str | None,
    *,
    version_label: str,
    repo_url: str | None,
    commit_sha: str | None,
    release_tag: str | None,
    summary: str,
    model_version: str | None,
    runtime_target: str | None,
    capabilities_snapshot: list[str],
    major_change: bool,
    breaking_change: bool,
    provenance_proofs: list[dict] | None = None,
    partner: str | None = None,
) -> dict:
    paths = workspace_paths(workspace)
    metadata = load_workspace(workspace)
    agent = metadata.get("agent", {})
    resolved_platform = (platform_url or metadata.get("platform_url") or "").rstrip("/")
    if not resolved_platform:
        raise SystemExit("platform_url is missing. Supply --platform or re-run init.")

    access_token = ensure_access_token(workspace, resolved_platform, required_scope="release:write", partner=partner)
    private_key = load_private_key(paths["private_key"])
    manifest = {
        "agent_id": agent["id"],
        "version_label": version_label,
        "repo_url": repo_url or "",
        "commit_sha": commit_sha or "",
        "release_tag": release_tag or "",
        "summary": summary,
        "model_version": model_version or "",
        "runtime_target": runtime_target or "",
        "capabilities_snapshot": capabilities_snapshot,
        "major_change": major_change,
        "breaking_change": breaking_change,
        "provenance_proofs": provenance_proofs or [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "nonce": f"release-{datetime.now(timezone.utc).timestamp()}",
    }
    signature = sign_claim(private_key, manifest)
    response = fetch_json(
        f"{resolved_platform}/api/v1/agents/{agent['id']}/releases",
        method="POST",
        payload={
            "release_manifest": manifest,
            "signature": signature,
            "access_token": access_token,
        },
    )

    releases_payload: list[dict] = []
    if paths["releases"].exists():
        releases_payload = load_json(paths["releases"])
    releases_payload.append(response)
    dump_json(paths["releases"], releases_payload)
    return response


def verify_release_manifest(
    workspace: Path,
    platform_url: str | None,
    *,
    release_id: str,
    summary: str,
    confidence: float,
    partner: str | None = None,
) -> dict:
    paths = workspace_paths(workspace)
    metadata = load_workspace(workspace)
    agent = metadata.get("agent", {})
    resolved_platform = (platform_url or metadata.get("platform_url") or "").rstrip("/")
    if not resolved_platform:
        raise SystemExit("platform_url is missing. Supply --platform or re-run init.")

    access_token = ensure_access_token(workspace, resolved_platform, required_scope="release:verify", partner=partner)
    private_key = load_private_key(paths["private_key"])
    claim = {
        "release_id": release_id,
        "issuer_agent_id": agent["id"],
        "summary": summary,
        "confidence": confidence,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "nonce": f"release-verify-{datetime.now(timezone.utc).timestamp()}",
    }
    signature = sign_claim(private_key, claim)
    return fetch_json(
        f"{resolved_platform}/api/v1/releases/{release_id}/verify",
        method="POST",
        payload={
            "issuer_agent_id": agent["id"],
            "verification_claim": claim,
            "signature": signature,
            "access_token": access_token,
        },
    )


def create_attestation(
    workspace: Path,
    platform_url: str | None,
    subject_agent_id: str | None,
    subject_handle: str | None,
    kind: str,
    summary: str,
    score_delta: float,
    confidence: float,
    evidence_url: str | None = None,
    interaction_ref: str | None = None,
    use_auth: bool = True,
) -> dict:
    paths = workspace_paths(workspace)
    metadata = load_workspace(workspace)
    agent = metadata.get("agent", {})
    resolved_platform = (platform_url or metadata.get("platform_url") or "").rstrip("/")
    if not resolved_platform:
        raise SystemExit("platform_url is missing. Supply --platform or re-run init.")

    resolved_subject_id = subject_agent_id
    resolved_subject_handle = subject_handle
    if not resolved_subject_id and resolved_subject_handle:
        resolved = resolve_agent_handle(resolved_platform, resolved_subject_handle)
        resolved_subject_id = resolved["agent"]["id"]
        resolved_subject_handle = resolved["agent"]["handle"]
    if not resolved_subject_id:
        raise SystemExit("Supply either --subject-agent-id or --subject-handle.")

    auth_proof = None
    access_token = None
    if use_auth:
        access_token = ensure_access_token(workspace, resolved_platform, required_scope="attest:write")
        if paths["auth_proof"].exists():
            auth_proof = load_json(paths["auth_proof"])

    private_key = load_private_key(paths["private_key"])
    claim = {
        "issuer_agent_id": agent["id"],
        "subject_agent_id": resolved_subject_id,
        "kind": kind,
        "summary": summary,
        "evidence_url": evidence_url or "",
        "interaction_ref": interaction_ref or "",
        "score_delta": score_delta,
        "confidence": confidence,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "nonce": f"attestation-{datetime.now(timezone.utc).timestamp()}",
    }
    signature = sign_claim(private_key, claim)
    response = fetch_json(
        f"{resolved_platform}/api/v1/attestations",
        method="POST",
        payload={
            "issuer_agent_id": agent["id"],
            "subject_agent_id": resolved_subject_id,
            "subject_handle": resolved_subject_handle,
            "kind": kind,
            "summary": summary,
            "evidence_url": evidence_url or "",
            "interaction_ref": interaction_ref or "",
            "score_delta": score_delta,
            "confidence": confidence,
            "attestation_claim": claim,
            "signature": signature,
            "auth_proof": auth_proof,
            "access_token": access_token,
        },
    )

    attestation_log_path = workspace / "attestations.json"
    log_payload: list[dict] = []
    if attestation_log_path.exists():
        log_payload = load_json(attestation_log_path)
    log_payload.append(response)
    dump_json(attestation_log_path, log_payload)
    return response


def update_profile(
    workspace: Path,
    platform_url: str | None,
    *,
    description: str | None,
    homepage_url: str | None,
    capabilities: list[str] | None,
    tags: list[str] | None,
    x_handle: str | None,
    x_url: str | None,
    github_handle: str | None,
    github_url: str | None,
    docs_url: str | None,
    support_url: str | None,
    evm_wallets: list[str] | None,
    solana_wallets: list[str] | None,
    proof_url: str | None,
    proof_note: str | None,
    recovery_public_keys: list[dict] | None,
    partner: str | None = "dashboard",
) -> dict:
    paths = workspace_paths(workspace)
    metadata = load_workspace(workspace)
    agent = metadata.get("agent", {})
    resolved_platform = (platform_url or metadata.get("platform_url") or "").rstrip("/")
    if not resolved_platform:
        raise SystemExit("platform_url is missing. Supply --platform or re-run init.")

    access_token = ensure_access_token(workspace, resolved_platform, required_scope="profile:write", partner=partner)
    wallet_claims = [
        {
            "chain": "erc20",
            "address": address,
            "label": f"EVM wallet {index + 1}",
        }
        for index, address in enumerate(evm_wallets or [])
    ] + [
        {
            "chain": "solana",
            "address": address,
            "label": f"Solana wallet {index + 1}",
        }
        for index, address in enumerate(solana_wallets or [])
    ]
    external_proofs = (
        [
            {
                "type": "profile_evidence",
                "value": proof_url,
                "status": "self_attested",
                "proof_url": proof_url,
                "notes": proof_note or "",
            }
        ]
        if proof_url
        else []
    )
    response = fetch_json(
        f"{resolved_platform}/api/v1/agents/{agent['id']}/profile",
        method="POST",
        payload={
            "description": description or agent.get("description", ""),
            "homepage_url": homepage_url or agent.get("homepage_url", ""),
            "capabilities": capabilities or agent.get("capabilities", []),
            "tags": tags or agent.get("tags", []),
            "profile_links": {
                "x_handle": x_handle or "",
                "x_url": x_url or "",
                "github_handle": github_handle or "",
                "github_url": github_url or "",
                "docs_url": docs_url or "",
                "support_url": support_url or "",
            },
            "wallet_claims": wallet_claims,
            "external_proofs": external_proofs,
            "recovery_public_keys": recovery_public_keys or metadata.get("recovery_public_keys", []),
            "access_token": access_token,
        },
    )
    dump_json(paths["passport"], response["passport"])
    metadata["agent"] = response["agent"]
    metadata["recovery_public_keys"] = recovery_public_keys or metadata.get("recovery_public_keys", [])
    metadata["profile_updated_at"] = datetime.now(timezone.utc).isoformat()
    dump_json(paths["agent"], metadata)
    return response


def post_bond(
    workspace: Path,
    platform_url: str | None,
    *,
    amount: float,
    reason: str,
    partner: str | None = None,
    evidence_url: str | None = None,
) -> dict:
    metadata = load_workspace(workspace)
    agent = metadata.get("agent", {})
    resolved_platform = (platform_url or metadata.get("platform_url") or "").rstrip("/")
    if not resolved_platform:
        raise SystemExit("platform_url is missing. Supply --platform or re-run init.")
    access_token = ensure_access_token(workspace, resolved_platform, required_scope="bond:write", partner=partner)
    response = fetch_json(
        f"{resolved_platform}/api/v1/agents/{agent['id']}/bond",
        method="POST",
        payload={
            "actor_agent_id": agent["id"],
            "amount": amount,
            "reason": reason,
            "partner": partner,
            "evidence_url": evidence_url or "",
            "source": "agent_runtime",
            "access_token": access_token,
        },
    )
    dump_json(workspace_paths(workspace)["economic"], response)
    return response


def manage_holdback(
    workspace: Path,
    platform_url: str | None,
    *,
    target_agent_id: str | None,
    target_handle: str | None,
    action: str,
    amount: float,
    reason: str,
    partner: str | None = None,
    evidence_url: str | None = None,
) -> dict:
    metadata = load_workspace(workspace)
    actor = metadata.get("agent", {})
    resolved_platform = (platform_url or metadata.get("platform_url") or "").rstrip("/")
    if not resolved_platform:
        raise SystemExit("platform_url is missing. Supply --platform or re-run init.")
    resolved_target_id = target_agent_id or actor.get("id")
    if not resolved_target_id and target_handle:
        resolved_target_id = resolve_agent_handle(resolved_platform, target_handle)["agent"]["id"]
    access_token = ensure_access_token(workspace, resolved_platform, required_scope="holdback:write", partner=partner)
    response = fetch_json(
        f"{resolved_platform}/api/v1/agents/{resolved_target_id}/holdbacks",
        method="POST",
        payload={
            "actor_agent_id": actor["id"],
            "action": action,
            "amount": amount,
            "reason": reason,
            "partner": partner,
            "evidence_url": evidence_url or "",
            "source": "agent_runtime",
            "access_token": access_token,
        },
    )
    dump_json(workspace_paths(workspace)["economic"], response)
    return response


def slash_agent(
    workspace: Path,
    platform_url: str | None,
    *,
    target_agent_id: str | None,
    target_handle: str | None,
    amount: float,
    reason: str,
    partner: str | None = None,
    evidence_url: str | None = None,
) -> dict:
    metadata = load_workspace(workspace)
    actor = metadata.get("agent", {})
    resolved_platform = (platform_url or metadata.get("platform_url") or "").rstrip("/")
    if not resolved_platform:
        raise SystemExit("platform_url is missing. Supply --platform or re-run init.")
    resolved_target_id = target_agent_id
    if not resolved_target_id and target_handle:
        resolved_target_id = resolve_agent_handle(resolved_platform, target_handle)["agent"]["id"]
    if not resolved_target_id:
        raise SystemExit("Supply either --target-agent-id or --target-handle.")
    access_token = ensure_access_token(workspace, resolved_platform, required_scope="slash:write", partner=partner)
    response = fetch_json(
        f"{resolved_platform}/api/v1/agents/{resolved_target_id}/slashes",
        method="POST",
        payload={
            "actor_agent_id": actor["id"],
            "amount": amount,
            "reason": reason,
            "partner": partner,
            "evidence_url": evidence_url or "",
            "source": "agent_runtime",
            "access_token": access_token,
        },
    )
    dump_json(workspace_paths(workspace)["economic"], response)
    return response


def open_dispute_case(
    workspace: Path,
    platform_url: str | None,
    *,
    subject_agent_id: str | None,
    subject_handle: str | None,
    category: str,
    title: str,
    summary: str,
    evidence_url: str | None = None,
    related_attestation_id: str | None = None,
    related_release_id: str | None = None,
    partner: str | None = None,
) -> dict:
    metadata = load_workspace(workspace)
    opener = metadata.get("agent", {})
    resolved_platform = (platform_url or metadata.get("platform_url") or "").rstrip("/")
    if not resolved_platform:
        raise SystemExit("platform_url is missing. Supply --platform or re-run init.")
    resolved_subject_id = subject_agent_id
    if not resolved_subject_id and subject_handle:
        resolved_subject_id = resolve_agent_handle(resolved_platform, subject_handle)["agent"]["id"]
    if not resolved_subject_id:
        raise SystemExit("Supply either --subject-agent-id or --subject-handle.")
    access_token = ensure_access_token(workspace, resolved_platform, required_scope="dispute:write", partner=partner)
    return fetch_json(
        f"{resolved_platform}/api/v1/disputes",
        method="POST",
        payload={
            "opened_by_agent_id": opener["id"],
            "subject_agent_id": resolved_subject_id,
            "category": category,
            "title": title,
            "summary": summary,
            "evidence_url": evidence_url or "",
            "related_attestation_id": related_attestation_id,
            "related_release_id": related_release_id,
            "partner": partner,
            "access_token": access_token,
        },
    )


def review_dispute_case(
    workspace: Path,
    platform_url: str | None,
    *,
    dispute_id: str,
    verdict: str,
    summary: str,
    recommended_slash_amount: float | None = None,
    partner: str | None = None,
) -> dict:
    metadata = load_workspace(workspace)
    reviewer = metadata.get("agent", {})
    resolved_platform = (platform_url or metadata.get("platform_url") or "").rstrip("/")
    if not resolved_platform:
        raise SystemExit("platform_url is missing. Supply --platform or re-run init.")
    access_token = ensure_access_token(workspace, resolved_platform, required_scope="review:write", partner=partner)
    return fetch_json(
        f"{resolved_platform}/api/v1/disputes/{dispute_id}/reviews",
        method="POST",
        payload={
            "reviewer_agent_id": reviewer["id"],
            "verdict": verdict,
            "summary": summary,
            "recommended_slash_amount": recommended_slash_amount,
            "partner": partner,
            "access_token": access_token,
        },
    )


def init_command(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    recovery_public_keys = load_recovery_public_keys(Path(args.recovery_key_file)) if args.recovery_key_file else []
    if args.private_key:
        import_existing_private_key(workspace, Path(args.private_key).expanduser().resolve())
    else:
        generate_identity(workspace)

    response = register_agent(
        workspace=workspace,
        platform_url=args.platform,
        name=args.name,
        description=args.description,
        homepage_url=args.homepage_url,
        capabilities=args.capabilities or [],
        tags=args.tags or [],
        moltbook_identity_token=args.moltbook_identity_token,
        recovery_public_keys=recovery_public_keys,
    )
    if recovery_public_keys:
        dump_json(workspace_paths(workspace)["recovery_keys"], recovery_public_keys)
    print(json.dumps(response, indent=2))
    return 0


def register_command(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    existing = load_workspace(workspace)
    existing_agent = existing.get("agent", {})
    recovery_public_keys = load_recovery_public_keys(Path(args.recovery_key_file)) if args.recovery_key_file else existing.get("recovery_public_keys", [])
    response = register_agent(
        workspace=workspace,
        platform_url=args.platform or existing.get("platform_url", ""),
        name=args.name or existing_agent.get("name", ""),
        description=args.description or existing_agent.get("description", ""),
        homepage_url=args.homepage_url if args.homepage_url is not None else existing_agent.get("homepage_url"),
        capabilities=args.capabilities or existing_agent.get("capabilities", []),
        tags=args.tags or existing_agent.get("tags", []),
        moltbook_identity_token=args.moltbook_identity_token,
        recovery_public_keys=recovery_public_keys,
    )
    if recovery_public_keys:
        dump_json(workspace_paths(workspace)["recovery_keys"], recovery_public_keys)
    print(json.dumps(response, indent=2))
    return 0


def auth_command(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    response = authenticate_agent_with_scopes(workspace, args.platform, args.scope, args.partner)
    print(json.dumps(response, indent=2))
    return 0


def refresh_command(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    response = refresh_session(workspace, args.platform)
    print(json.dumps(response, indent=2))
    return 0


def revoke_command(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    response = revoke_session(workspace, args.platform)
    print(json.dumps(response, indent=2))
    return 0


def attest_command(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    response = create_attestation(
        workspace=workspace,
        platform_url=args.platform,
        subject_agent_id=args.subject_agent_id,
        subject_handle=args.subject_handle,
        kind=args.kind,
        summary=args.summary,
        score_delta=args.score_delta,
        confidence=args.confidence,
        evidence_url=args.evidence_url,
        interaction_ref=args.interaction_ref,
        use_auth=not args.no_auth,
    )
    print(json.dumps(response, indent=2))
    return 0


def update_profile_command(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    recovery_public_keys = load_recovery_public_keys(Path(args.recovery_key_file)) if args.recovery_key_file else None
    response = update_profile(
        workspace=workspace,
        platform_url=args.platform,
        description=args.description,
        homepage_url=args.homepage_url,
        capabilities=args.capabilities,
        tags=args.tags,
        x_handle=args.x_handle,
        x_url=args.x_url,
        github_handle=args.github_handle,
        github_url=args.github_url,
        docs_url=args.docs_url,
        support_url=args.support_url,
        evm_wallets=args.evm_wallet or [],
        solana_wallets=args.solana_wallet or [],
        proof_url=args.proof_url,
        proof_note=args.proof_note,
        recovery_public_keys=recovery_public_keys,
        partner=args.partner,
    )
    if recovery_public_keys:
        dump_json(workspace_paths(workspace)["recovery_keys"], recovery_public_keys)
    print(json.dumps(response, indent=2))
    return 0


def publish_release_command(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    capabilities_snapshot = args.capability or load_workspace(workspace).get("agent", {}).get("capabilities", [])
    provenance_proofs = []
    for item in args.provenance_proof or []:
        proof_type, _, value = item.partition("=")
        if proof_type and value:
            provenance_proofs.append({"type": proof_type, "value": value})
    response = publish_release(
        workspace=workspace,
        platform_url=args.platform,
        version_label=args.version_label,
        repo_url=args.repo_url,
        commit_sha=args.commit_sha,
        release_tag=args.release_tag,
        summary=args.summary,
        model_version=args.model_version,
        runtime_target=args.runtime_target,
        capabilities_snapshot=capabilities_snapshot,
        major_change=args.major_change,
        breaking_change=args.breaking_change,
        provenance_proofs=provenance_proofs,
        partner=args.partner,
    )
    print(json.dumps(response, indent=2))
    return 0


def rotate_key_command(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    response = rotate_agent_key(
        workspace=workspace,
        platform_url=args.platform,
        new_private_key_path=Path(args.new_private_key).expanduser().resolve() if args.new_private_key else None,
    )
    print(json.dumps(response, indent=2))
    return 0


def recover_key_command(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    response = recover_agent_key(
        workspace=workspace,
        platform_url=args.platform,
        recovery_private_key_path=Path(args.recovery_private_key).expanduser().resolve(),
        recovery_key_id=args.recovery_key_id,
        new_private_key_path=Path(args.new_private_key).expanduser().resolve() if args.new_private_key else None,
    )
    print(json.dumps(response, indent=2))
    return 0


def verify_release_command(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    response = verify_release_manifest(
        workspace=workspace,
        platform_url=args.platform,
        release_id=args.release_id,
        summary=args.summary,
        confidence=args.confidence,
        partner=args.partner,
    )
    print(json.dumps(response, indent=2))
    return 0


def post_bond_command(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    response = post_bond(
        workspace=workspace,
        platform_url=args.platform,
        amount=args.amount,
        reason=args.reason,
        partner=args.partner,
        evidence_url=args.evidence_url,
    )
    print(json.dumps(response, indent=2))
    return 0


def holdback_command(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    response = manage_holdback(
        workspace=workspace,
        platform_url=args.platform,
        target_agent_id=args.target_agent_id,
        target_handle=args.target_handle,
        action=args.action,
        amount=args.amount,
        reason=args.reason,
        partner=args.partner,
        evidence_url=args.evidence_url,
    )
    print(json.dumps(response, indent=2))
    return 0


def slash_command(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    response = slash_agent(
        workspace=workspace,
        platform_url=args.platform,
        target_agent_id=args.target_agent_id,
        target_handle=args.target_handle,
        amount=args.amount,
        reason=args.reason,
        partner=args.partner,
        evidence_url=args.evidence_url,
    )
    print(json.dumps(response, indent=2))
    return 0


def dispute_command(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    response = open_dispute_case(
        workspace=workspace,
        platform_url=args.platform,
        subject_agent_id=args.subject_agent_id,
        subject_handle=args.subject_handle,
        category=args.category,
        title=args.title,
        summary=args.summary,
        evidence_url=args.evidence_url,
        related_attestation_id=args.related_attestation_id,
        related_release_id=args.related_release_id,
        partner=args.partner,
    )
    print(json.dumps(response, indent=2))
    return 0


def review_dispute_command(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    response = review_dispute_case(
        workspace=workspace,
        platform_url=args.platform,
        dispute_id=args.dispute_id,
        verdict=args.verdict,
        summary=args.summary,
        recommended_slash_amount=args.recommended_slash_amount,
        partner=args.partner,
    )
    print(json.dumps(response, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AgentTrust runtime client")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Generate or import a persistent key and register the agent")
    init_parser.add_argument("--workspace", required=True, help="Folder where agent.json, passport.json and keys are stored")
    init_parser.add_argument("--platform", required=True, help="AgentTrust base URL, e.g. http://127.0.0.1:5000")
    init_parser.add_argument("--name", required=True)
    init_parser.add_argument("--description", required=True)
    init_parser.add_argument("--homepage-url")
    init_parser.add_argument("--capabilities", nargs="*", default=[])
    init_parser.add_argument("--tags", nargs="*", default=[])
    init_parser.add_argument("--moltbook-identity-token", help="Optional temporary Moltbook identity token for verified registration")
    init_parser.add_argument("--private-key", help="Import an existing PKCS8 PEM private key instead of generating a new one")
    init_parser.add_argument("--recovery-key-file", help="Path to a JSON array of recovery public keys")
    init_parser.set_defaults(func=init_command)

    register_parser = subparsers.add_parser("register", help="Register again using an existing local identity workspace")
    register_parser.add_argument("--workspace", required=True)
    register_parser.add_argument("--platform", help="Override stored platform URL")
    register_parser.add_argument("--name")
    register_parser.add_argument("--description")
    register_parser.add_argument("--homepage-url")
    register_parser.add_argument("--capabilities", nargs="*")
    register_parser.add_argument("--tags", nargs="*")
    register_parser.add_argument("--moltbook-identity-token", help="Optional temporary Moltbook identity token for verified registration")
    register_parser.add_argument("--recovery-key-file", help="Path to a JSON array of recovery public keys")
    register_parser.set_defaults(func=register_command)

    auth_parser = subparsers.add_parser("auth", help="Request a fresh platform auth proof for an existing agent workspace")
    auth_parser.add_argument("--workspace", required=True)
    auth_parser.add_argument("--platform", help="Override stored platform URL")
    auth_parser.add_argument("--scope", action="append", help="Request a scope such as attest:write or marketplace:access")
    auth_parser.add_argument("--partner", help="Optional partner namespace for the session")
    auth_parser.set_defaults(func=auth_command)

    login_parser = subparsers.add_parser("login", help="Login from the runtime and receive fresh access/refresh tokens")
    login_parser.add_argument("--workspace", required=True)
    login_parser.add_argument("--platform", help="Override stored platform URL")
    login_parser.add_argument("--scope", action="append", help="Request a scope such as attest:write or marketplace:access")
    login_parser.add_argument("--partner", help="Optional partner namespace for the session")
    login_parser.set_defaults(func=auth_command)

    refresh_parser = subparsers.add_parser("refresh", help="Refresh runtime session tokens using the stored refresh token")
    refresh_parser.add_argument("--workspace", required=True)
    refresh_parser.add_argument("--platform", help="Override stored platform URL")
    refresh_parser.set_defaults(func=refresh_command)

    revoke_parser = subparsers.add_parser("logout", help="Revoke the stored refresh session and remove local session artifacts")
    revoke_parser.add_argument("--workspace", required=True)
    revoke_parser.add_argument("--platform", help="Override stored platform URL")
    revoke_parser.set_defaults(func=revoke_command)

    attest_parser = subparsers.add_parser("attest", help="Sign and publish an attestation from the runtime workspace")
    attest_parser.add_argument("--workspace", required=True)
    attest_parser.add_argument("--platform", help="Override stored platform URL")
    attest_parser.add_argument("--subject-agent-id")
    attest_parser.add_argument("--subject-handle")
    attest_parser.add_argument("--kind", required=True)
    attest_parser.add_argument("--summary", required=True)
    attest_parser.add_argument("--score-delta", type=float, required=True)
    attest_parser.add_argument("--confidence", type=float, required=True)
    attest_parser.add_argument("--evidence-url")
    attest_parser.add_argument("--interaction-ref")
    attest_parser.add_argument("--no-auth", action="store_true", help="Skip the fresh auth-proof flow")
    attest_parser.set_defaults(func=attest_command)

    profile_parser = subparsers.add_parser("update-profile", help="Update public profile claims for the current agent")
    profile_parser.add_argument("--workspace", required=True)
    profile_parser.add_argument("--platform", help="Override stored platform URL")
    profile_parser.add_argument("--description")
    profile_parser.add_argument("--homepage-url")
    profile_parser.add_argument("--capabilities", nargs="*")
    profile_parser.add_argument("--tags", nargs="*")
    profile_parser.add_argument("--x-handle")
    profile_parser.add_argument("--x-url")
    profile_parser.add_argument("--github-handle")
    profile_parser.add_argument("--github-url")
    profile_parser.add_argument("--docs-url")
    profile_parser.add_argument("--support-url")
    profile_parser.add_argument("--evm-wallet", action="append")
    profile_parser.add_argument("--solana-wallet", action="append")
    profile_parser.add_argument("--proof-url")
    profile_parser.add_argument("--proof-note")
    profile_parser.add_argument("--recovery-key-file", help="Path to a JSON array of recovery public keys")
    profile_parser.add_argument("--partner", default="dashboard")
    profile_parser.set_defaults(func=update_profile_command)

    publish_release_parser = subparsers.add_parser("publish-release", help="Publish a signed release manifest for the current agent")
    publish_release_parser.add_argument("--workspace", required=True)
    publish_release_parser.add_argument("--platform", help="Override stored platform URL")
    publish_release_parser.add_argument("--version-label", required=True)
    publish_release_parser.add_argument("--repo-url")
    publish_release_parser.add_argument("--commit-sha")
    publish_release_parser.add_argument("--release-tag")
    publish_release_parser.add_argument("--summary", required=True)
    publish_release_parser.add_argument("--model-version")
    publish_release_parser.add_argument("--runtime-target")
    publish_release_parser.add_argument("--capability", action="append", help="Capability snapshot value")
    publish_release_parser.add_argument("--provenance-proof", action="append", help="Provenance proof in the form type=value")
    publish_release_parser.add_argument("--major-change", action="store_true")
    publish_release_parser.add_argument("--breaking-change", action="store_true")
    publish_release_parser.add_argument("--partner", help="Optional partner namespace for scoped login")
    publish_release_parser.set_defaults(func=publish_release_command)

    rotate_key_parser = subparsers.add_parser("rotate-key", help="Rotate the active agent key while preserving identity continuity")
    rotate_key_parser.add_argument("--workspace", required=True)
    rotate_key_parser.add_argument("--platform", help="Override stored platform URL")
    rotate_key_parser.add_argument("--new-private-key", help="Optional path to an existing PKCS8 PEM private key")
    rotate_key_parser.set_defaults(func=rotate_key_command)

    recover_key_parser = subparsers.add_parser("recover-key", help="Recover the agent identity using a registered recovery key")
    recover_key_parser.add_argument("--workspace", required=True)
    recover_key_parser.add_argument("--platform", help="Override stored platform URL")
    recover_key_parser.add_argument("--recovery-private-key", required=True, help="Path to the registered recovery private key")
    recover_key_parser.add_argument("--recovery-key-id", required=True, help="The recovery key_id registered with AgentLayer")
    recover_key_parser.add_argument("--new-private-key", help="Optional path to an existing PKCS8 PEM private key")
    recover_key_parser.set_defaults(func=recover_key_command)

    verify_release_parser = subparsers.add_parser("verify-release", help="Verify another agent's published release manifest")
    verify_release_parser.add_argument("--workspace", required=True)
    verify_release_parser.add_argument("--platform", help="Override stored platform URL")
    verify_release_parser.add_argument("--release-id", required=True)
    verify_release_parser.add_argument("--summary", required=True)
    verify_release_parser.add_argument("--confidence", type=float, default=0.85)
    verify_release_parser.add_argument("--partner", help="Optional partner namespace for scoped login")
    verify_release_parser.set_defaults(func=verify_release_command)

    bond_parser = subparsers.add_parser("post-bond", help="Post collateral bond for the current agent")
    bond_parser.add_argument("--workspace", required=True)
    bond_parser.add_argument("--platform", help="Override stored platform URL")
    bond_parser.add_argument("--amount", type=float, required=True)
    bond_parser.add_argument("--reason", required=True)
    bond_parser.add_argument("--partner", help="Optional partner namespace for scoped login")
    bond_parser.add_argument("--evidence-url")
    bond_parser.set_defaults(func=post_bond_command)

    holdback_parser = subparsers.add_parser("holdback", help="Lock or release holdback against an agent bond account")
    holdback_parser.add_argument("--workspace", required=True)
    holdback_parser.add_argument("--platform", help="Override stored platform URL")
    holdback_parser.add_argument("--action", choices=["lock", "release"], required=True)
    holdback_parser.add_argument("--amount", type=float, required=True)
    holdback_parser.add_argument("--reason", required=True)
    holdback_parser.add_argument("--target-agent-id")
    holdback_parser.add_argument("--target-handle")
    holdback_parser.add_argument("--partner", help="Optional partner namespace for scoped login")
    holdback_parser.add_argument("--evidence-url")
    holdback_parser.set_defaults(func=holdback_command)

    slash_parser = subparsers.add_parser("slash", help="Slash another agent's posted collateral")
    slash_parser.add_argument("--workspace", required=True)
    slash_parser.add_argument("--platform", help="Override stored platform URL")
    slash_parser.add_argument("--target-agent-id")
    slash_parser.add_argument("--target-handle")
    slash_parser.add_argument("--amount", type=float, required=True)
    slash_parser.add_argument("--reason", required=True)
    slash_parser.add_argument("--partner", help="Optional partner namespace for scoped login")
    slash_parser.add_argument("--evidence-url")
    slash_parser.set_defaults(func=slash_command)

    dispute_parser = subparsers.add_parser("open-dispute", help="Open a dispute case against another agent")
    dispute_parser.add_argument("--workspace", required=True)
    dispute_parser.add_argument("--platform", help="Override stored platform URL")
    dispute_parser.add_argument("--subject-agent-id")
    dispute_parser.add_argument("--subject-handle")
    dispute_parser.add_argument("--category", required=True)
    dispute_parser.add_argument("--title", required=True)
    dispute_parser.add_argument("--summary", required=True)
    dispute_parser.add_argument("--evidence-url")
    dispute_parser.add_argument("--related-attestation-id")
    dispute_parser.add_argument("--related-release-id")
    dispute_parser.add_argument("--partner", help="Optional partner namespace for scoped login")
    dispute_parser.set_defaults(func=dispute_command)

    review_parser = subparsers.add_parser("review-dispute", help="Review an open dispute as a higher-trust reviewer")
    review_parser.add_argument("--workspace", required=True)
    review_parser.add_argument("--platform", help="Override stored platform URL")
    review_parser.add_argument("--dispute-id", required=True)
    review_parser.add_argument("--verdict", choices=["uphold", "dismiss"], required=True)
    review_parser.add_argument("--summary", required=True)
    review_parser.add_argument("--recommended-slash-amount", type=float)
    review_parser.add_argument("--partner", help="Optional partner namespace for scoped login")
    review_parser.set_defaults(func=review_dispute_command)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
