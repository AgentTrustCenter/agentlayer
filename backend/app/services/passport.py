from __future__ import annotations

from typing import Any

from .canonical import PASSPORT_SCHEMA_VERSION
from .crypto import sign_platform_payload
from .policy import agent_eligibility


def build_agent_passport(agent, platform_url: str, platform_signing_key, platform_public_key: str) -> dict[str, Any]:
    eligibility = agent_eligibility(agent)
    payload = {
        "schema_version": PASSPORT_SCHEMA_VERSION,
        "passport_version": "1.1",
        "agent_id": agent.id,
        "handle": agent.handle,
        "name": agent.name,
        "description": agent.description,
        "homepage_url": agent.homepage_url,
        "capabilities": agent.capabilities,
        "tags": agent.tags,
        "profile_links": agent.profile_links or {},
        "wallet_claims": agent.wallet_claims or [],
        "external_proofs": agent.external_proofs or [],
        "key_algorithm": agent.key_algorithm,
        "identity_version": agent.identity_version,
        "active_key_id": agent.active_key_id or agent.public_key_fingerprint,
        "key_history": agent.key_history or [],
        "recovery_public_keys": [
            {
                "key_id": item.get("key_id"),
                "algorithm": item.get("algorithm"),
                "label": item.get("label"),
            }
            for item in (agent.recovery_public_keys or [])
        ],
        "public_key_fingerprint": agent.public_key_fingerprint,
        "public_profile_url": f"{platform_url}/agents/{agent.id}",
        "api_profile_url": f"{platform_url}/api/v1/agents/{agent.id}",
        "creation_timestamp": agent.created_at.isoformat(),
        "trust_score": round(eligibility["effective_trust_score"], 2),
        "base_trust_score": round(eligibility["base_trust_score"], 2),
        "trust_lenses": eligibility["trust_lenses"],
        "sybil_risk_score": eligibility["sybil_risk_score"],
        "verification_status": eligibility["verification_status"],
        "access_tier": eligibility["access_tier"],
        "eligibility": eligibility["eligibility"],
        "economic_security": eligibility["economic_security"],
        "latest_release": eligibility["latest_release"],
        "release_warning_active": eligibility["release_warning_active"],
        "registry": "AgentTrust",
    }
    return {
        "payload": payload,
        "platform_signature": sign_platform_payload(platform_signing_key, payload),
        "platform_public_key": platform_public_key,
        "platform_signature_algorithm": "Ed25519",
    }
