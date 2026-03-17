from __future__ import annotations

import hashlib
from typing import Any


PASSPORT_SCHEMA_VERSION = "agent_passport/v1"
ATTESTATION_SCHEMA_VERSION = "attestation_event/v1"
RELEASE_SCHEMA_VERSION = "release_manifest/v1"
DISPUTE_SCHEMA_VERSION = "dispute_case/v1"
KEY_ROTATION_SCHEMA_VERSION = "key_rotation/v1"
KEY_RECOVERY_SCHEMA_VERSION = "key_recovery/v1"

TRUST_LENS_NAMES = ("execution", "payment", "research")


def default_trust_lenses() -> dict[str, float]:
    return {lens: 50.0 for lens in TRUST_LENS_NAMES}


def sha256_text(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def normalize_evidence_bundle(payload: Any, *, fallback_url: str | None = None) -> dict[str, Any] | None:
    if isinstance(payload, str):
        pointer_url = payload.strip() or None
        return (
            {
                "pointer_url": pointer_url,
                "sha256": None,
                "mime_type": None,
                "redaction_level": "pointer_only",
                "contains_personal_data": False,
                "notes": None,
            }
            if pointer_url
            else None
        )

    if not isinstance(payload, dict):
        pointer_url = (fallback_url or "").strip() or None
        return (
            {
                "pointer_url": pointer_url,
                "sha256": None,
                "mime_type": None,
                "redaction_level": "pointer_only",
                "contains_personal_data": False,
                "notes": None,
            }
            if pointer_url
            else None
        )

    pointer_url = str(payload.get("pointer_url") or fallback_url or "").strip() or None
    raw_text = str(payload.get("raw_text") or "").strip() or None
    sha256 = str(payload.get("sha256") or "").strip() or sha256_text(raw_text)
    bundle = {
        "pointer_url": pointer_url,
        "sha256": sha256,
        "mime_type": str(payload.get("mime_type") or "").strip() or None,
        "redaction_level": str(payload.get("redaction_level") or "minimized").strip() or "minimized",
        "contains_personal_data": bool(payload.get("contains_personal_data", False)),
        "notes": str(payload.get("notes") or "").strip() or None,
    }
    if not any(bundle.values()):
        return None
    return bundle


def normalize_provenance_proofs(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    proofs: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        proof_type = str(item.get("type") or "").strip()
        value = str(item.get("value") or "").strip()
        if not proof_type or not value:
            continue
        proofs.append(
            {
                "type": proof_type,
                "value": value,
                "verified": bool(item.get("verified", False)),
                "issuer": str(item.get("issuer") or "").strip() or None,
                "notes": str(item.get("notes") or "").strip() or None,
            }
        )
    return proofs


def normalize_recovery_public_keys(payload: Any) -> list[dict[str, str]]:
    if not isinstance(payload, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        key_id = str(item.get("key_id") or "").strip()
        public_key_pem = str(item.get("public_key_pem") or "").strip()
        algorithm = str(item.get("algorithm") or "ECDSA_P256_SHA256").strip() or "ECDSA_P256_SHA256"
        label = str(item.get("label") or "").strip() or key_id
        if not key_id or not public_key_pem:
            continue
        normalized.append(
            {
                "key_id": key_id,
                "public_key_pem": public_key_pem,
                "algorithm": algorithm,
                "label": label,
            }
        )
    return normalized
