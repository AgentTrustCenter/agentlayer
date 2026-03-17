from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import urllib.parse
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, redirect, request

from ..db import db
from ..models import (
    Agent,
    AgentKeyEvent,
    AgentRelease,
    AgentSession,
    Attestation,
    AuditEvent,
    BondEvent,
    DisputeCase,
    DisputeReview,
    ExternalVerificationSession,
    ReleaseVerification,
)
from ..services.audit import record_audit_event, serialize_audit_event
from ..services.auth import (
    allowed_scopes_for_tier,
    auth_proof_is_valid,
    create_agent_auth_challenge,
    create_auth_proof,
    create_session_tokens,
    new_session_ids,
    normalize_requested_scopes,
    session_token_is_valid,
    verify_signed_platform_payload,
)
from ..services.canonical import (
    ATTESTATION_SCHEMA_VERSION,
    DISPUTE_SCHEMA_VERSION,
    KEY_RECOVERY_SCHEMA_VERSION,
    KEY_ROTATION_SCHEMA_VERSION,
    RELEASE_SCHEMA_VERSION,
    normalize_evidence_bundle,
    normalize_provenance_proofs,
    normalize_recovery_public_keys,
    sha256_text,
)
from ..services.crypto import (
    fingerprint_public_key,
    verify_agent_signature,
    verify_platform_signature,
)
from ..services.disputes import (
    apply_opening_holdback,
    dispute_rule_for_category,
    dispute_rules,
    maybe_resolve_dispute,
    recommended_holdback_amount,
    recommended_slash_amount,
    serialize_dispute_case,
    serialize_dispute_review,
)
from ..services.moltbook import MoltbookVerificationError, verify_moltbook_identity
from ..services.economic import (
    economic_policy,
    economic_posture,
    record_bond_event,
    serialize_bond_account,
    serialize_bond_event,
)
from ..services.passport import build_agent_passport
from ..services.policy import (
    access_tier_meets,
    agent_eligibility,
    create_registration_challenge,
    evaluate_partner_access,
    integration_examples,
    network_policy,
    partner_policies,
    partner_policy_for,
    registration_quickstart,
)
from ..services.proofs import (
    create_oauth_session,
    create_wallet_verification_session,
    exchange_github_code,
    exchange_x_code,
    github_authorize_url,
    verify_evm_wallet_signature,
    verify_solana_wallet_signature,
    wallet_message_from_payload,
    x_authorize_url,
)
from ..services.releases import agent_release_posture, serialize_release
from ..services.scoring import EVENT_LENS_WEIGHTS, issuer_credibility, recalculate_network_scores


api_bp = Blueprint("api", __name__, url_prefix="/api/v1")


SUPPORTED_CHAINS = {
    "erc20": "Ethereum / ERC20",
    "evm": "EVM",
    "solana": "Solana",
}


def _slugify(value: str) -> str:
    filtered = "".join(char.lower() if char.isalnum() else "-" for char in value)
    slug = "-".join(part for part in filtered.split("-") if part)
    return slug[:60] or "agent"


def _serialize_agent(agent: Agent) -> dict:
    platform_url = current_app.config["PLATFORM_URL"]
    eligibility = agent_eligibility(agent)
    return {
        "id": agent.id,
        "handle": agent.handle,
        "name": agent.name,
        "description": agent.description,
        "homepage_url": agent.homepage_url,
        "capabilities": agent.capabilities,
        "tags": agent.tags,
        "profile_links": agent.profile_links or {},
        "wallet_claims": agent.wallet_claims or [],
        "external_proofs": agent.external_proofs or [],
        "public_key_fingerprint": agent.public_key_fingerprint,
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
        "trust_score": round(eligibility["effective_trust_score"], 2),
        "base_trust_score": round(eligibility["base_trust_score"], 2),
        "trust_lenses": eligibility["trust_lenses"],
        "sybil_risk_score": eligibility["sybil_risk_score"],
        "incoming_attestations_count": agent.incoming_attestations_count,
        "outgoing_attestations_count": agent.outgoing_attestations_count,
        "created_at": agent.created_at.isoformat(),
        "updated_at": agent.updated_at.isoformat(),
        "status": agent.status,
        "profile_url": f"{platform_url}/agents/{agent.id}",
        "api_url": f"{platform_url}/api/v1/agents/{agent.id}",
        **eligibility,
    }


def _serialize_attestation(attestation: Attestation) -> dict:
    return {
        "schema_version": attestation.schema_version or ATTESTATION_SCHEMA_VERSION,
        "id": attestation.id,
        "issuer_agent_id": attestation.issuer_agent_id,
        "subject_agent_id": attestation.subject_agent_id,
        "kind": attestation.kind,
        "summary": attestation.summary,
        "evidence_url": attestation.evidence_url,
        "evidence_hash": attestation.evidence_hash,
        "evidence_bundle": attestation.evidence_bundle or {},
        "interaction_ref": attestation.interaction_ref,
        "confidence": attestation.confidence,
        "score_delta": attestation.score_delta,
        "trust_lenses": attestation.trust_lenses or {},
        "issuer_credibility": round(float(attestation.issuer_credibility or 0.0), 2),
        "created_at": attestation.created_at.isoformat(),
        "signed_payload": attestation.signed_payload,
    }


def _error(message: str, status_code: int = 400):
    return jsonify({"error": message}), status_code


def _trim_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_profile_links(payload: dict | None) -> dict:
    if not isinstance(payload, dict):
        return {}
    normalized = {}
    for key in ["x_handle", "x_url", "github_handle", "github_url", "docs_url", "support_url"]:
        value = _trim_text(payload.get(key))
        if value:
            normalized[key] = value
    return normalized


def _normalize_wallet_claims(payload: Any) -> list[dict]:
    if not isinstance(payload, list):
        return []
    claims = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        chain = (_trim_text(item.get("chain")) or "").lower()
        address = _trim_text(item.get("address"))
        if chain not in SUPPORTED_CHAINS or not address:
            continue
        claims.append(
            {
                "chain": chain,
                "chain_label": SUPPORTED_CHAINS[chain],
                "address": address,
                "label": _trim_text(item.get("label")) or SUPPORTED_CHAINS[chain],
                "status": _trim_text(item.get("status")) or "self_attested",
                "proof_method": _trim_text(item.get("proof_method")) or "owner_key_claim",
                "proof_value": _trim_text(item.get("proof_value")),
                "verified_at": _trim_text(item.get("verified_at")),
            }
        )
    return claims


def _normalize_external_proofs(payload: Any) -> list[dict]:
    if not isinstance(payload, list):
        return []
    proofs = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        proof_type = _trim_text(item.get("type"))
        value = _trim_text(item.get("value"))
        if not proof_type or not value:
            continue
        proofs.append(
            {
                "type": proof_type,
                "value": value,
                "status": _trim_text(item.get("status")) or "self_attested",
                "proof_url": _trim_text(item.get("proof_url")),
                "notes": _trim_text(item.get("notes")),
                "issuer": _trim_text(item.get("issuer")),
                "verified": bool(item.get("verified", _trim_text(item.get("status")) == "verified")),
            }
        )
    return proofs


def _upsert_wallet_claim(agent: Agent, wallet_claim: dict) -> list[dict]:
    claims = list(agent.wallet_claims or [])
    replaced = False
    for index, existing in enumerate(claims):
        if existing.get("chain") == wallet_claim.get("chain") and existing.get("address", "").lower() == wallet_claim.get("address", "").lower():
            claims[index] = {**existing, **wallet_claim}
            replaced = True
            break
    if not replaced:
        claims.append(wallet_claim)
    return claims


def _upsert_external_proof(agent: Agent, proof: dict) -> list[dict]:
    proofs = list(agent.external_proofs or [])
    replaced = False
    for index, existing in enumerate(proofs):
        if existing.get("type") == proof.get("type"):
            proofs[index] = {**existing, **proof}
            replaced = True
            break
    if not replaced:
        proofs.append(proof)
    return proofs


def _append_key_history(agent: Agent, fingerprint: str, public_key_pem: str, *, event_type: str):
    history = list(agent.key_history or [])
    history.append(
        {
            "fingerprint": fingerprint,
            "public_key_pem": public_key_pem,
            "event_type": event_type,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    agent.key_history = history[-12:]


def _find_recovery_key(agent: Agent, key_id: str | None):
    if not key_id:
        return None
    for item in agent.recovery_public_keys or []:
        if item.get("key_id") == key_id:
            return item
    return None


def _sorted_agents_by_effective_score(agents: list[Agent]) -> list[Agent]:
    return sorted(
        agents,
        key=lambda agent: (
            agent_release_posture(agent)["effective_trust_score"],
            int(agent.incoming_attestations_count or 0),
        ),
        reverse=True,
    )


def _session_by_refresh_token(refresh_token: dict | None):
    if not refresh_token:
        return None
    payload = refresh_token.get("payload") or {}
    token_id = payload.get("token_id")
    if not token_id:
        return None
    return AgentSession.query.filter_by(refresh_token_id=token_id).first()


def _session_for_access_token(access_token: dict | None, *, agent_id: str, required_scope: str):
    if not access_token:
        return None
    session = AgentSession.query.filter_by(id=access_token.get("payload", {}).get("session_id")).first()
    is_valid = session_token_is_valid(
        current_app.platform_public_key_pem,
        access_token,
        agent_id=agent_id,
        expected_kind="access",
        required_scope=required_scope,
        session=session,
    )
    if not is_valid:
        return None
    return session


@api_bp.get("/health")
def health():
    return jsonify({"status": "ok", "service": "AgentTrust API", "database": current_app.config["SQLALCHEMY_DATABASE_URI"].split(":", 1)[0], "time": datetime.now(timezone.utc).isoformat()})


@api_bp.get("/ops/metrics")
def ops_metrics():
    return jsonify(
        {
            "agents": Agent.query.count(),
            "attestations": Attestation.query.count(),
            "releases": AgentRelease.query.count(),
            "disputes_open": DisputeCase.query.filter_by(status="open").count(),
            "sessions_active": AgentSession.query.filter_by(revoked_at=None).count(),
            "audit_events": AuditEvent.query.count(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


@api_bp.get("/registration/quickstart")
def get_registration_quickstart():
    return jsonify(registration_quickstart(current_app.config["PLATFORM_URL"]))


@api_bp.post("/auth/challenge")
def agent_auth_challenge():
    payload = request.get_json(silent=True) or {}
    agent_id = payload.get("agent_id")
    if not agent_id:
        return _error("agent_id is required.")
    agent = Agent.query.get(agent_id)
    if not agent:
        return _error("Agent not found.", 404)
    challenge = create_agent_auth_challenge(current_app.platform_signing_key, agent.id)
    return jsonify(
        {
            **challenge,
            "platform_public_key": current_app.platform_public_key_pem,
            "required_claim_field": "challenge_nonce",
        }
    )


@api_bp.post("/auth/verify")
def agent_auth_verify():
    payload = request.get_json(silent=True) or {}
    required = ["agent_id", "auth_claim", "signature", "challenge"]
    missing = [field for field in required if not payload.get(field)]
    if missing:
        return _error(f"Missing required fields: {', '.join(missing)}")

    agent = Agent.query.get(payload["agent_id"])
    if not agent:
        return _error("Agent not found.", 404)

    challenge = payload["challenge"]
    challenge_payload = challenge.get("payload")
    challenge_signature = challenge.get("platform_signature")
    if not challenge_payload or not challenge_signature:
        return _error("Challenge payload and platform signature are required.")
    if not verify_signed_platform_payload(current_app.platform_public_key_pem, challenge_payload, challenge_signature):
        return _error("Invalid auth challenge signature.", 401)
    if challenge_payload.get("agent_id") != agent.id or challenge_payload.get("purpose") != "agent_authentication":
        return _error("Invalid auth challenge payload.")
    try:
        challenge_expiry = datetime.fromisoformat(challenge_payload["expires_at"].replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return _error("Invalid auth challenge expiry.")
    if datetime.now(timezone.utc) > challenge_expiry:
        return _error("Auth challenge expired. Request a fresh challenge.")

    claim = payload["auth_claim"]
    if claim.get("agent_id") != agent.id or claim.get("challenge_nonce") != challenge_payload.get("nonce"):
        return _error("Auth claim does not match the challenge.")
    timestamp_text = claim.get("timestamp")
    if not timestamp_text:
        return _error("Auth claim requires an ISO timestamp.")
    try:
        claim_timestamp = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
    except ValueError:
        return _error("Invalid auth claim timestamp.")
    if datetime.now(timezone.utc) - claim_timestamp > timedelta(minutes=10):
        return _error("Auth claim expired. Sign a fresh auth claim.")
    if not verify_agent_signature(agent.public_key_pem, claim, payload["signature"]):
        return _error("Invalid agent auth signature.", 401)

    eligibility = agent_eligibility(agent)
    partner = (payload.get("partner") or "").strip() or None
    scopes = normalize_requested_scopes(eligibility["access_tier"], payload.get("requested_scopes"))
    partner_policy = partner_policy_for(partner, current_app.config["PLATFORM_URL"])
    if partner_policy:
        if not access_tier_meets(eligibility["access_tier"], partner_policy["min_access_tier"]):
            return _error(
                f"Partner '{partner}' requires at least {partner_policy['min_access_tier']} tier access.",
                403,
            )
        allowed_for_partner = set(partner_policy["allowed_scopes"])
        requested_scopes = payload.get("requested_scopes") or []
        if requested_scopes:
            rejected_scopes = [scope for scope in requested_scopes if scope not in allowed_for_partner]
            if rejected_scopes:
                return _error(
                    f"Partner '{partner}' does not allow scopes: {', '.join(rejected_scopes)}",
                    403,
                )
            scopes = [scope for scope in scopes if scope in allowed_for_partner]
        else:
            scopes = [
                scope for scope in partner_policy.get("default_scopes", []) if scope in scopes
            ]
        if not scopes:
            return _error(f"No eligible scopes remain for partner '{partner}'.", 403)

    session_id, refresh_token_id = new_session_ids()
    session_tokens = create_session_tokens(
        current_app.platform_signing_key,
        agent,
        session_id=session_id,
        refresh_token_id=refresh_token_id,
        partner=partner,
        scopes=scopes,
    )
    refresh_payload = session_tokens["refresh_token"]["payload"]
    db.session.add(
        AgentSession(
            id=session_id,
            agent_id=agent.id,
            partner=partner,
            scopes=scopes,
            refresh_token_id=refresh_token_id,
            refresh_expires_at=datetime.fromisoformat(refresh_payload["expires_at"].replace("Z", "+00:00")),
        )
    )
    record_audit_event(
        db,
        event_type="session_created",
        agent_id=agent.id,
        actor_agent_id=agent.id,
        partner=partner,
        event_payload={"scopes": scopes, "session_id": session_id},
    )
    db.session.commit()

    auth_proof = create_auth_proof(current_app.platform_signing_key, agent)
    auth_proof["payload"]["access_tier"] = eligibility["access_tier"]
    return jsonify(
        {
            "agent": _serialize_agent(agent),
            "auth_proof": auth_proof,
            "session_tokens": session_tokens,
            "granted_scopes": scopes,
            "allowed_scopes": allowed_scopes_for_tier(eligibility["access_tier"]),
            "partner": partner,
            "partner_policy": partner_policy,
            "platform_public_key": current_app.platform_public_key_pem,
        }
    )


@api_bp.post("/auth/refresh")
def agent_auth_refresh():
    payload = request.get_json(silent=True) or {}
    refresh_token = payload.get("refresh_token")
    if not refresh_token:
        return _error("refresh_token is required.")
    token_payload = refresh_token.get("payload") or {}
    agent_id = token_payload.get("agent_id")
    if not agent_id:
        return _error("refresh_token payload is missing agent_id.")
    agent = Agent.query.get(agent_id)
    if not agent:
        return _error("Agent not found.", 404)
    session = _session_by_refresh_token(refresh_token)
    if not session:
        return _error("Refresh session not found.", 404)
    if not session_token_is_valid(
        current_app.platform_public_key_pem,
        refresh_token,
        agent_id=agent.id,
        expected_kind="refresh",
        session=session,
    ):
        return _error("Invalid or expired refresh token.", 401)
    if datetime.now(timezone.utc) > session.refresh_expires_at or session.revoked_at is not None:
        return _error("Refresh session expired or revoked.", 401)
    refresh_token_id = str(uuid4())
    session_tokens = create_session_tokens(
        current_app.platform_signing_key,
        agent,
        session_id=session.id,
        refresh_token_id=refresh_token_id,
        partner=session.partner,
        scopes=session.scopes,
    )
    refresh_payload = session_tokens["refresh_token"]["payload"]
    session.refresh_token_id = refresh_token_id
    session.refresh_expires_at = datetime.fromisoformat(refresh_payload["expires_at"].replace("Z", "+00:00"))
    session.last_refreshed_at = datetime.now(timezone.utc)
    record_audit_event(
        db,
        event_type="session_refreshed",
        agent_id=agent.id,
        actor_agent_id=agent.id,
        partner=session.partner,
        event_payload={"session_id": session.id},
    )
    db.session.commit()
    return jsonify(
        {
            "agent": _serialize_agent(agent),
            "session_tokens": session_tokens,
            "granted_scopes": session.scopes,
            "partner": session.partner,
            "platform_public_key": current_app.platform_public_key_pem,
        }
    )


@api_bp.post("/auth/revoke")
def agent_auth_revoke():
    payload = request.get_json(silent=True) or {}
    refresh_token = payload.get("refresh_token")
    session = _session_by_refresh_token(refresh_token)
    if not session:
        return _error("Refresh session not found.", 404)
    session.revoked_at = datetime.now(timezone.utc)
    record_audit_event(
        db,
        event_type="session_revoked",
        agent_id=session.agent_id,
        actor_agent_id=session.agent_id,
        partner=session.partner,
        event_payload={"session_id": session.id},
    )
    db.session.commit()
    return jsonify({"revoked": True, "session_id": session.id})


@api_bp.post("/registration/challenge")
def registration_challenge():
    challenge = create_registration_challenge(current_app.platform_signing_key)
    return jsonify(
        {
            **challenge,
            "platform_public_key": current_app.platform_public_key_pem,
            "required_claim_field": "challenge_nonce",
        }
    )


@api_bp.get("/network/policy")
def get_network_policy():
    return jsonify(network_policy(current_app.config["PLATFORM_URL"]))


@api_bp.get("/partners/policies")
def get_partner_policies():
    base_url = current_app.config["PLATFORM_URL"]
    return jsonify(
        {
            "partner_policies": partner_policies(base_url),
            "integration_examples": integration_examples(base_url),
        }
    )


@api_bp.get("/partners/policies/<partner>")
def get_partner_policy_detail(partner: str):
    policy = partner_policy_for(partner, current_app.config["PLATFORM_URL"])
    if not policy:
        return _error("Partner policy not found.", 404)
    return jsonify({"partner_policy": policy})


@api_bp.get("/agents/<agent_id>/partner-evaluation/<partner>")
def get_partner_evaluation(agent_id: str, partner: str):
    agent = Agent.query.get_or_404(agent_id)
    return jsonify(evaluate_partner_access(agent, partner, current_app.config["PLATFORM_URL"]))


@api_bp.get("/economic-security")
def get_economic_security():
    agents = Agent.query.all()
    top_bonded_agents = sorted(
        agents,
        key=lambda agent: economic_posture(agent)["net_bonded_balance"],
        reverse=True,
    )[:6]
    recent_events = BondEvent.query.order_by(BondEvent.created_at.desc()).limit(12).all()
    return jsonify(
        {
            "policy": economic_policy(),
            "top_bonded_agents": [_serialize_agent(agent) for agent in top_bonded_agents],
            "recent_events": [serialize_bond_event(event) for event in recent_events],
        }
    )


@api_bp.get("/disputes")
def list_disputes():
    status = request.args.get("status")
    query = DisputeCase.query.order_by(DisputeCase.created_at.desc())
    if status:
        query = query.filter_by(status=status)
    disputes = query.limit(40).all()
    return jsonify(
        {
            "rules": dispute_rules(),
            "disputes": [serialize_dispute_case(dispute) for dispute in disputes],
        }
    )


@api_bp.get("/audit/events")
def list_audit_events():
    query = AuditEvent.query.order_by(AuditEvent.created_at.desc())
    agent_id = request.args.get("agent_id")
    if agent_id:
        query = query.filter_by(agent_id=agent_id)
    events = query.limit(100).all()
    return jsonify({"events": [serialize_audit_event(event) for event in events]})


@api_bp.get("/agents")
def list_agents():
    agents = _sorted_agents_by_effective_score(Agent.query.all())
    return jsonify({"agents": [_serialize_agent(agent) for agent in agents]})


@api_bp.get("/agents/resolve/<handle>")
def resolve_agent_by_handle(handle: str):
    agent = Agent.query.filter_by(handle=handle).first()
    if not agent:
        return _error("Agent handle not found.", 404)
    return jsonify({"agent": _serialize_agent(agent)})


@api_bp.get("/agents/<agent_id>/releases")
def list_agent_releases(agent_id: str):
    Agent.query.get_or_404(agent_id)
    releases = (
        AgentRelease.query.filter_by(agent_id=agent_id)
        .order_by(AgentRelease.created_at.desc())
        .all()
    )
    return jsonify({"releases": [serialize_release(item) for item in releases]})


@api_bp.get("/agents/<agent_id>/economic-security")
def get_agent_economic_security(agent_id: str):
    agent = Agent.query.get_or_404(agent_id)
    events = BondEvent.query.filter_by(agent_id=agent.id).order_by(BondEvent.created_at.desc()).limit(20).all()
    return jsonify(
        {
            "agent": _serialize_agent(agent),
            "bond_account": serialize_bond_account(agent.bond_account),
            "events": [serialize_bond_event(event) for event in events],
            "policy": economic_policy(),
        }
    )


@api_bp.get("/agents/<agent_id>/disputes")
def get_agent_disputes(agent_id: str):
    agent = Agent.query.get_or_404(agent_id)
    disputes = DisputeCase.query.filter_by(subject_agent_id=agent.id).order_by(DisputeCase.created_at.desc()).limit(20).all()
    return jsonify({"agent": _serialize_agent(agent), "disputes": [serialize_dispute_case(dispute) for dispute in disputes]})


@api_bp.route("/agents/<agent_id>/profile", methods=["GET", "POST"])
def manage_agent_profile(agent_id: str):
    agent = Agent.query.get_or_404(agent_id)
    if request.method == "GET":
        return jsonify(
            {
                "agent": _serialize_agent(agent),
                "editable_fields": [
                    "description",
                    "homepage_url",
                    "capabilities",
                    "tags",
                    "profile_links",
                    "wallet_claims",
                    "external_proofs",
                    "recovery_public_keys",
                ],
                "owner_console": network_policy(current_app.config["PLATFORM_URL"])["owner_console"],
            }
        )

    payload = request.get_json(silent=True) or {}
    session = _session_for_access_token(payload.get("access_token"), agent_id=agent.id, required_scope="profile:write")
    if not session:
        return _error("Invalid or expired access token for profile updates.", 401)

    agent.description = _trim_text(payload.get("description")) or agent.description
    agent.homepage_url = _trim_text(payload.get("homepage_url"))
    capabilities = payload.get("capabilities")
    tags = payload.get("tags")
    if isinstance(capabilities, list):
        agent.capabilities = [str(item).strip() for item in capabilities if str(item).strip()]
    if isinstance(tags, list):
        agent.tags = [str(item).strip() for item in tags if str(item).strip()]
    agent.profile_links = _normalize_profile_links(payload.get("profile_links"))
    agent.wallet_claims = _normalize_wallet_claims(payload.get("wallet_claims"))
    agent.external_proofs = _normalize_external_proofs(payload.get("external_proofs"))
    recovery_public_keys = normalize_recovery_public_keys(payload.get("recovery_public_keys"))
    if recovery_public_keys:
        agent.recovery_public_keys = recovery_public_keys
    record_audit_event(
        db,
        event_type="profile_updated",
        agent_id=agent.id,
        actor_agent_id=agent.id,
        partner=session.partner,
        event_payload={
            "updated_fields": [field for field in ["description", "homepage_url", "capabilities", "tags", "profile_links", "wallet_claims", "external_proofs", "recovery_public_keys"] if payload.get(field) is not None],
        },
    )
    db.session.commit()

    passport = build_agent_passport(
        agent,
        current_app.config["PLATFORM_URL"],
        current_app.platform_signing_key,
        current_app.platform_public_key_pem,
    )
    return jsonify({"agent": _serialize_agent(agent), "passport": passport}), 200


@api_bp.get("/agents/<agent_id>/keys")
def get_agent_keys(agent_id: str):
    agent = Agent.query.get_or_404(agent_id)
    events = AgentKeyEvent.query.filter_by(agent_id=agent.id).order_by(AgentKeyEvent.created_at.desc()).all()
    return jsonify(
        {
            "agent_id": agent.id,
            "identity_version": agent.identity_version,
            "active_key_id": agent.active_key_id or agent.public_key_fingerprint,
            "active_public_key_fingerprint": agent.public_key_fingerprint,
            "recovery_public_keys": [
                {k: v for k, v in item.items() if k != "public_key_pem"} for item in (agent.recovery_public_keys or [])
            ],
            "history": agent.key_history or [],
            "events": [
                {
                    "id": event.id,
                    "event_type": event.event_type,
                    "previous_public_key_fingerprint": event.previous_public_key_fingerprint,
                    "new_public_key_fingerprint": event.new_public_key_fingerprint,
                    "recovery_key_id": event.recovery_key_id,
                    "created_at": event.created_at.isoformat(),
                }
                for event in events
            ],
        }
    )


@api_bp.post("/agents/<agent_id>/keys/rotate")
def rotate_agent_key(agent_id: str):
    agent = Agent.query.get_or_404(agent_id)
    payload = request.get_json(silent=True) or {}
    required = ["new_public_key_pem", "rotation_claim", "signature"]
    missing = [field for field in required if not payload.get(field)]
    if missing:
        return _error(f"Missing required fields: {', '.join(missing)}")

    claim = payload["rotation_claim"]
    new_public_key_pem = str(payload["new_public_key_pem"]).strip()
    new_fingerprint = fingerprint_public_key(new_public_key_pem)
    if Agent.query.filter(Agent.public_key_fingerprint == new_fingerprint, Agent.id != agent.id).first():
        return _error("This new public key is already registered to another agent.", 409)
    if claim.get("schema_version") not in {None, KEY_ROTATION_SCHEMA_VERSION}:
        return _error("Unsupported key rotation schema version.")
    if claim.get("agent_id") != agent.id:
        return _error("Rotation claim agent_id does not match target agent.")
    if claim.get("previous_public_key_fingerprint") != agent.public_key_fingerprint:
        return _error("Rotation claim previous fingerprint does not match the active key.")
    if claim.get("new_public_key_fingerprint") != new_fingerprint:
        return _error("Rotation claim new fingerprint does not match the supplied key.")
    timestamp_text = claim.get("timestamp")
    if not timestamp_text:
        return _error("Rotation claim requires an ISO timestamp.")
    try:
        claim_timestamp = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
    except ValueError:
        return _error("Invalid key rotation timestamp.")
    if datetime.now(timezone.utc) - claim_timestamp > timedelta(hours=1):
        return _error("Rotation claim expired. Sign a fresh payload.")
    if not verify_agent_signature(agent.public_key_pem, claim, payload["signature"]):
        return _error("Invalid active-key signature for key rotation.", 401)

    previous_fingerprint = agent.public_key_fingerprint
    previous_public_key = agent.public_key_pem
    _append_key_history(agent, previous_fingerprint, previous_public_key, event_type="rotated_out")
    agent.public_key_pem = new_public_key_pem
    agent.public_key_fingerprint = new_fingerprint
    agent.active_key_id = new_fingerprint
    agent.identity_version = int(agent.identity_version or 1) + 1
    key_event = AgentKeyEvent(
        agent_id=agent.id,
        event_type="rotation",
        previous_public_key_fingerprint=previous_fingerprint,
        new_public_key_fingerprint=new_fingerprint,
        claim_payload=claim,
        actor_signature=payload["signature"],
    )
    db.session.add(key_event)
    record_audit_event(
        db,
        event_type="key_rotated",
        agent_id=agent.id,
        actor_agent_id=agent.id,
        severity="warning",
        event_payload={
            "previous_public_key_fingerprint": previous_fingerprint,
            "new_public_key_fingerprint": new_fingerprint,
            "identity_version": agent.identity_version,
        },
    )
    db.session.commit()
    passport = build_agent_passport(agent, current_app.config["PLATFORM_URL"], current_app.platform_signing_key, current_app.platform_public_key_pem)
    return jsonify({"agent": _serialize_agent(agent), "passport": passport}), 200


@api_bp.post("/agents/<agent_id>/keys/recover")
def recover_agent_key(agent_id: str):
    agent = Agent.query.get_or_404(agent_id)
    payload = request.get_json(silent=True) or {}
    required = ["new_public_key_pem", "recovery_claim", "signature", "recovery_key_id"]
    missing = [field for field in required if not payload.get(field)]
    if missing:
        return _error(f"Missing required fields: {', '.join(missing)}")

    claim = payload["recovery_claim"]
    recovery_key_id = str(payload["recovery_key_id"]).strip()
    recovery_key = _find_recovery_key(agent, recovery_key_id)
    if not recovery_key:
        return _error("Recovery key not found for this agent.", 404)
    new_public_key_pem = str(payload["new_public_key_pem"]).strip()
    new_fingerprint = fingerprint_public_key(new_public_key_pem)
    if Agent.query.filter(Agent.public_key_fingerprint == new_fingerprint, Agent.id != agent.id).first():
        return _error("This new public key is already registered to another agent.", 409)
    if claim.get("schema_version") not in {None, KEY_RECOVERY_SCHEMA_VERSION}:
        return _error("Unsupported key recovery schema version.")
    if claim.get("agent_id") != agent.id or claim.get("recovery_key_id") != recovery_key_id:
        return _error("Recovery claim does not match agent or recovery key.")
    if claim.get("new_public_key_fingerprint") != new_fingerprint:
        return _error("Recovery claim new fingerprint does not match the supplied key.")
    timestamp_text = claim.get("timestamp")
    if not timestamp_text:
        return _error("Recovery claim requires an ISO timestamp.")
    try:
        claim_timestamp = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
    except ValueError:
        return _error("Invalid key recovery timestamp.")
    if datetime.now(timezone.utc) - claim_timestamp > timedelta(hours=1):
        return _error("Recovery claim expired. Sign a fresh payload.")
    if not verify_agent_signature(recovery_key["public_key_pem"], claim, payload["signature"]):
        return _error("Invalid recovery-key signature.", 401)

    previous_fingerprint = agent.public_key_fingerprint
    previous_public_key = agent.public_key_pem
    _append_key_history(agent, previous_fingerprint, previous_public_key, event_type="recovered_out")
    agent.public_key_pem = new_public_key_pem
    agent.public_key_fingerprint = new_fingerprint
    agent.active_key_id = new_fingerprint
    agent.identity_version = int(agent.identity_version or 1) + 1
    key_event = AgentKeyEvent(
        agent_id=agent.id,
        event_type="recovery",
        previous_public_key_fingerprint=previous_fingerprint,
        new_public_key_fingerprint=new_fingerprint,
        recovery_key_id=recovery_key_id,
        claim_payload=claim,
        actor_signature=payload["signature"],
    )
    db.session.add(key_event)
    record_audit_event(
        db,
        event_type="key_recovered",
        agent_id=agent.id,
        severity="critical",
        event_payload={
            "previous_public_key_fingerprint": previous_fingerprint,
            "new_public_key_fingerprint": new_fingerprint,
            "recovery_key_id": recovery_key_id,
            "identity_version": agent.identity_version,
        },
    )
    db.session.commit()
    passport = build_agent_passport(agent, current_app.config["PLATFORM_URL"], current_app.platform_signing_key, current_app.platform_public_key_pem)
    return jsonify({"agent": _serialize_agent(agent), "passport": passport}), 200


@api_bp.post("/agents/<agent_id>/proofs/wallet/challenge")
def create_wallet_proof_challenge(agent_id: str):
    agent = Agent.query.get_or_404(agent_id)
    payload = request.get_json(silent=True) or {}
    session = _session_for_access_token(payload.get("access_token"), agent_id=agent.id, required_scope="proof:write")
    if not session:
        return _error("Invalid or expired access token for wallet proof creation.", 401)

    chain = (_trim_text(payload.get("chain")) or "").lower()
    address = _trim_text(payload.get("address"))
    if chain not in SUPPORTED_CHAINS or not address:
        return _error("Supported chain and address are required.")

    verification_session = create_wallet_verification_session(agent, chain, address)
    db.session.add(verification_session)
    db.session.commit()
    message = wallet_message_from_payload(verification_session.challenge_payload)
    return jsonify(
        {
            "challenge_id": verification_session.id,
            "provider": chain,
            "address": address,
            "message": message,
            "challenge_payload": verification_session.challenge_payload,
            "expires_at": verification_session.expires_at.isoformat(),
        }
    )


@api_bp.post("/agents/<agent_id>/proofs/wallet/verify")
def verify_wallet_proof(agent_id: str):
    agent = Agent.query.get_or_404(agent_id)
    payload = request.get_json(silent=True) or {}
    session = _session_for_access_token(payload.get("access_token"), agent_id=agent.id, required_scope="proof:write")
    if not session:
        return _error("Invalid or expired access token for wallet verification.", 401)

    challenge_id = _trim_text(payload.get("challenge_id"))
    signature = _trim_text(payload.get("signature"))
    if not challenge_id or not signature:
        return _error("challenge_id and signature are required.")

    verification_session = ExternalVerificationSession.query.get(challenge_id)
    if not verification_session or verification_session.agent_id != agent.id or verification_session.session_kind != "wallet":
        return _error("Wallet verification challenge not found.", 404)
    if verification_session.consumed_at is not None:
        return _error("Wallet verification challenge has already been consumed.", 409)
    if datetime.now(timezone.utc) > verification_session.expires_at:
        return _error("Wallet verification challenge expired.", 410)

    challenge_payload = verification_session.challenge_payload or {}
    message = wallet_message_from_payload(challenge_payload)
    chain = challenge_payload.get("chain")
    address = challenge_payload.get("address")
    try:
        if chain in {"erc20", "evm"}:
            valid = verify_evm_wallet_signature(message, signature, address)
        elif chain == "solana":
            valid = verify_solana_wallet_signature(message, signature, address)
        else:
            return _error("Unsupported wallet verification chain.")
    except Exception as exc:
        return _error(f"Wallet signature verification failed: {exc}", 400)
    if not valid:
        return _error("Wallet signature did not match the claimed address.", 401)

    verification_session.consumed_at = datetime.now(timezone.utc)
    verified_claim = {
        "chain": chain,
        "chain_label": SUPPORTED_CHAINS[chain],
        "address": address,
        "label": SUPPORTED_CHAINS[chain],
        "status": "verified",
        "proof_method": "wallet_signature",
        "proof_value": challenge_id,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }
    agent.wallet_claims = _upsert_wallet_claim(agent, verified_claim)
    agent.external_proofs = _upsert_external_proof(
        agent,
        {
            "type": f"{chain}_wallet_signature",
            "value": address,
            "status": "verified",
            "proof_url": None,
            "notes": f"Verified by signed wallet challenge {challenge_id}.",
        },
    )
    record_audit_event(
        db,
        event_type="wallet_verified",
        agent_id=agent.id,
        actor_agent_id=agent.id,
        partner=session.partner,
        event_payload={"chain": chain, "address": address},
    )
    db.session.commit()
    return jsonify({"agent": _serialize_agent(agent), "verified_wallet": verified_claim}), 200


@api_bp.post("/agents/<agent_id>/proofs/<provider>/start")
def start_social_proof(agent_id: str, provider: str):
    agent = Agent.query.get_or_404(agent_id)
    payload = request.get_json(silent=True) or {}
    session = _session_for_access_token(payload.get("access_token"), agent_id=agent.id, required_scope="proof:write")
    if not session:
        return _error("Invalid or expired access token for social verification.", 401)

    normalized_provider = provider.strip().lower()
    verification_session = create_oauth_session(agent, normalized_provider)
    db.session.add(verification_session)
    db.session.commit()

    if normalized_provider == "github":
        if not current_app.config["GITHUB_CLIENT_ID"] or not current_app.config["GITHUB_CLIENT_SECRET"]:
            return _error("GitHub OAuth is not configured on this deployment.", 503)
        authorize_url = github_authorize_url(
            current_app.config["GITHUB_CLIENT_ID"],
            current_app.config["GITHUB_REDIRECT_URI"],
            verification_session,
        )
    elif normalized_provider == "x":
        if not current_app.config["X_CLIENT_ID"]:
            return _error("X OAuth is not configured on this deployment.", 503)
        authorize_url = x_authorize_url(
            current_app.config["X_CLIENT_ID"],
            current_app.config["X_REDIRECT_URI"],
            verification_session,
        )
    else:
        return _error("Unsupported proof provider.", 404)

    return jsonify(
        {
            "provider": normalized_provider,
            "authorize_url": authorize_url,
            "state": verification_session.state,
            "expires_at": verification_session.expires_at.isoformat(),
        }
    )


@api_bp.get("/oauth/<provider>/callback")
def oauth_callback(provider: str):
    normalized_provider = provider.strip().lower()
    state = request.args.get("state")
    code = request.args.get("code")
    error = request.args.get("error")
    redirect_base = current_app.config["FRONTEND_APP_URL"].rstrip("/")
    def _redirect_with(status: str, reason: str | None = None, *, agent_id: str | None = None):
        query = {"verification": normalized_provider, "status": status}
        if reason:
            query["reason"] = reason
        if agent_id:
            query["agent_id"] = agent_id
        return redirect(f"{redirect_base}/?{urllib.parse.urlencode(query)}#owner-console")
    if error:
        return _redirect_with("error", error)
    if not state or not code:
        return _redirect_with("error", "missing_code")

    verification_session = ExternalVerificationSession.query.filter_by(state=state, provider=normalized_provider, session_kind="oauth").first()
    if not verification_session:
        return _redirect_with("error", "unknown_state")
    if verification_session.consumed_at is not None or datetime.now(timezone.utc) > verification_session.expires_at:
        return _redirect_with("error", "expired_state")

    agent = Agent.query.get(verification_session.agent_id)
    if not agent:
        return _redirect_with("error", "agent_not_found")

    try:
        if normalized_provider == "github":
            identity = exchange_github_code(
                code,
                client_id=current_app.config["GITHUB_CLIENT_ID"],
                client_secret=current_app.config["GITHUB_CLIENT_SECRET"],
                redirect_uri=current_app.config["GITHUB_REDIRECT_URI"],
            )
            profile_links = dict(agent.profile_links or {})
            profile_links["github_handle"] = identity["login"]
            profile_links["github_url"] = identity["profile_url"]
            agent.profile_links = profile_links
            agent.external_proofs = _upsert_external_proof(
                agent,
                {
                    "type": "github_oauth",
                    "value": identity["login"],
                    "status": "verified",
                    "proof_url": identity["profile_url"],
                    "notes": f"Verified through GitHub OAuth for user id {identity['id']}.",
                },
            )
        elif normalized_provider == "x":
            identity = exchange_x_code(
                code,
                client_id=current_app.config["X_CLIENT_ID"],
                client_secret=current_app.config["X_CLIENT_SECRET"] or None,
                redirect_uri=current_app.config["X_REDIRECT_URI"],
                code_verifier=verification_session.code_verifier or "",
            )
            profile_links = dict(agent.profile_links or {})
            profile_links["x_handle"] = identity["username"]
            profile_links["x_url"] = identity["profile_url"]
            agent.profile_links = profile_links
            agent.external_proofs = _upsert_external_proof(
                agent,
                {
                    "type": "x_oauth",
                    "value": identity["username"],
                    "status": "verified",
                    "proof_url": identity["profile_url"],
                    "notes": f"Verified through X OAuth for user id {identity['id']}.",
                },
            )
        else:
            return _redirect_with("error", "unsupported_provider")
    except Exception as exc:
        return _redirect_with("error", str(exc)[:120])

    verification_session.consumed_at = datetime.now(timezone.utc)
    record_audit_event(
        db,
        event_type=f"{normalized_provider}_verified",
        agent_id=agent.id,
        actor_agent_id=agent.id,
        event_payload={"provider": normalized_provider},
    )
    db.session.commit()
    return _redirect_with("success", agent_id=agent.id)


@api_bp.post("/disputes")
def open_dispute():
    payload = request.get_json(silent=True) or {}
    required = ["opened_by_agent_id", "subject_agent_id", "category", "title", "summary"]
    missing = [field for field in required if payload.get(field) in (None, "")]
    if missing:
        return _error(f"Missing required fields: {', '.join(missing)}")

    opener = Agent.query.get(payload["opened_by_agent_id"])
    subject = Agent.query.get(payload["subject_agent_id"])
    if not opener or not subject:
        return _error("Opening or subject agent not found.", 404)
    if opener.id == subject.id:
        return _error("Agents cannot open disputes against themselves.")

    session = _session_for_access_token(payload.get("access_token"), agent_id=opener.id, required_scope="dispute:write")
    if not session:
        return _error("Invalid or expired access token for dispute creation.", 401)

    category = str(payload["category"]).strip()
    rule = dispute_rule_for_category(category)
    evidence_bundle = normalize_evidence_bundle(payload.get("evidence"), fallback_url=(payload.get("evidence_url") or "").strip() or None)
    dispute = DisputeCase(
        subject_agent_id=subject.id,
        opened_by_agent_id=opener.id,
        category=category,
        severity=(payload.get("severity") or rule["severity"]).strip(),
        title=str(payload["title"]).strip(),
        summary=str(payload["summary"]).strip(),
        evidence_url=(payload.get("evidence_url") or "").strip() or None,
        schema_version=DISPUTE_SCHEMA_VERSION,
        evidence_hash=(evidence_bundle or {}).get("sha256"),
        evidence_bundle=evidence_bundle,
        privacy_redaction=str(payload.get("privacy_redaction") or "minimized").strip() or "minimized",
        related_attestation_id=payload.get("related_attestation_id") or None,
        related_release_id=payload.get("related_release_id") or None,
        auto_holdback_amount=recommended_holdback_amount(subject, category),
        recommended_slash_amount=recommended_slash_amount(subject, category),
    )
    db.session.add(dispute)
    db.session.flush()

    holdback_result = apply_opening_holdback(dispute, opener_agent_id=opener.id)
    if holdback_result:
        account, event = holdback_result
        if account is not None:
            db.session.add(account)
        if event is not None:
            db.session.add(event)
    record_audit_event(
        db,
        event_type="dispute_opened",
        agent_id=subject.id,
        actor_agent_id=opener.id,
        partner=session.partner,
        severity="warning",
        event_payload={"dispute_id": dispute.id, "category": category},
    )
    db.session.commit()
    return jsonify({"dispute": serialize_dispute_case(dispute), "subject": _serialize_agent(subject)}), 201


@api_bp.post("/disputes/<dispute_id>/reviews")
def review_dispute(dispute_id: str):
    dispute = DisputeCase.query.get_or_404(dispute_id)
    payload = request.get_json(silent=True) or {}
    required = ["reviewer_agent_id", "verdict", "summary"]
    missing = [field for field in required if payload.get(field) in (None, "")]
    if missing:
        return _error(f"Missing required fields: {', '.join(missing)}")
    if dispute.status != "open":
        return _error("This dispute is already resolved.", 409)

    reviewer = Agent.query.get(payload["reviewer_agent_id"])
    if not reviewer:
        return _error("Reviewer agent not found.", 404)
    if reviewer.id in {dispute.subject_agent_id, dispute.opened_by_agent_id}:
        return _error("Subject and opening agents cannot review the same dispute.")
    if DisputeReview.query.filter_by(dispute_id=dispute.id, reviewer_agent_id=reviewer.id).first():
        return _error("This reviewer has already submitted a review.", 409)

    session = _session_for_access_token(payload.get("access_token"), agent_id=reviewer.id, required_scope="review:write")
    if not session:
        return _error("Invalid or expired access token for dispute review.", 401)

    reviewer_eligibility = agent_eligibility(reviewer)
    if reviewer_eligibility["access_tier"] not in {"marketplace", "settlement"}:
        return _error("Reviewer must be at marketplace or settlement tier.", 403)

    verdict = str(payload["verdict"]).strip().lower()
    if verdict not in {"uphold", "dismiss"}:
        return _error("verdict must be either uphold or dismiss.")

    review = DisputeReview(
        dispute_id=dispute.id,
        reviewer_agent_id=reviewer.id,
        verdict=verdict,
        summary=str(payload["summary"]).strip(),
        recommended_slash_amount=float(payload.get("recommended_slash_amount") or 0.0),
    )
    db.session.add(review)
    db.session.flush()

    resolution = maybe_resolve_dispute(dispute)
    if resolution:
        account, event = resolution
        if account is not None:
            db.session.add(account)
        if event is not None:
            db.session.add(event)
    record_audit_event(
        db,
        event_type="dispute_review_submitted",
        agent_id=dispute.subject_agent_id,
        actor_agent_id=reviewer.id,
        partner=session.partner,
        severity="info",
        event_payload={"dispute_id": dispute.id, "verdict": verdict},
    )
    db.session.commit()
    return jsonify({"review": serialize_dispute_review(review), "dispute": serialize_dispute_case(dispute)}), 201


@api_bp.post("/agents/<agent_id>/bond")
def post_agent_bond(agent_id: str):
    agent = Agent.query.get_or_404(agent_id)
    payload = request.get_json(silent=True) or {}
    amount = payload.get("amount")
    reason = (payload.get("reason") or "").strip()
    if amount in (None, "") or not reason:
        return _error("amount and reason are required.")

    actor_agent_id = payload.get("actor_agent_id") or agent.id
    actor = Agent.query.get(actor_agent_id)
    if not actor or actor.id != agent.id:
        return _error("In this prototype, bond posting is self-funded by the target agent.", 400)

    session = _session_for_access_token(payload.get("access_token"), agent_id=actor.id, required_scope="bond:write")
    if not session:
        return _error("Invalid or expired access token for bond posting.", 401)

    try:
        account, event = record_bond_event(
            agent,
            event_type="bond_posted",
            amount=float(amount),
            reason=reason,
            actor_agent_id=actor.id,
            partner=payload.get("partner") or session.partner,
            evidence_url=payload.get("evidence_url"),
            event_payload={"source": payload.get("source") or "runtime"},
        )
    except ValueError as exc:
        return _error(str(exc))

    db.session.add(account)
    db.session.add(event)
    record_audit_event(
        db,
        event_type="bond_posted",
        agent_id=agent.id,
        actor_agent_id=actor.id,
        partner=payload.get("partner") or session.partner,
        event_payload={"amount": float(amount), "reason": reason},
    )
    db.session.commit()
    return jsonify({"agent": _serialize_agent(agent), "bond_account": serialize_bond_account(account), "event": serialize_bond_event(event)}), 201


@api_bp.post("/agents/<agent_id>/holdbacks")
def manage_agent_holdback(agent_id: str):
    agent = Agent.query.get_or_404(agent_id)
    payload = request.get_json(silent=True) or {}
    amount = payload.get("amount")
    reason = (payload.get("reason") or "").strip()
    action = (payload.get("action") or "").strip().lower()
    actor_agent_id = payload.get("actor_agent_id") or agent.id
    if amount in (None, "") or not reason or action not in {"lock", "release"}:
        return _error("action (lock or release), amount, and reason are required.")

    actor = Agent.query.get(actor_agent_id)
    if not actor:
        return _error("Actor agent not found.", 404)
    session = _session_for_access_token(payload.get("access_token"), agent_id=actor.id, required_scope="holdback:write")
    if not session:
        return _error("Invalid or expired access token for holdback management.", 401)

    try:
        account, event = record_bond_event(
            agent,
            event_type="holdback_locked" if action == "lock" else "holdback_released",
            amount=float(amount),
            reason=reason,
            actor_agent_id=actor.id,
            partner=payload.get("partner") or session.partner,
            evidence_url=payload.get("evidence_url"),
            event_payload={"action": action, "source": payload.get("source") or "runtime"},
        )
    except ValueError as exc:
        return _error(str(exc))

    db.session.add(account)
    db.session.add(event)
    record_audit_event(
        db,
        event_type=f"holdback_{action}",
        agent_id=agent.id,
        actor_agent_id=actor.id,
        partner=payload.get("partner") or session.partner,
        event_payload={"amount": float(amount), "reason": reason},
    )
    db.session.commit()
    return jsonify({"agent": _serialize_agent(agent), "bond_account": serialize_bond_account(account), "event": serialize_bond_event(event)}), 201


@api_bp.post("/agents/<agent_id>/slashes")
def slash_agent_bond(agent_id: str):
    agent = Agent.query.get_or_404(agent_id)
    payload = request.get_json(silent=True) or {}
    amount = payload.get("amount")
    reason = (payload.get("reason") or "").strip()
    actor_agent_id = payload.get("actor_agent_id")
    if amount in (None, "") or not reason or not actor_agent_id:
        return _error("actor_agent_id, amount, and reason are required.")

    actor = Agent.query.get(actor_agent_id)
    if not actor:
        return _error("Actor agent not found.", 404)
    if actor.id == agent.id:
        return _error("Agents cannot slash their own collateral.")
    session = _session_for_access_token(payload.get("access_token"), agent_id=actor.id, required_scope="slash:write")
    if not session:
        return _error("Invalid or expired access token for slashing.", 401)

    try:
        account, event = record_bond_event(
            agent,
            event_type="slash_applied",
            amount=float(amount),
            reason=reason,
            actor_agent_id=actor.id,
            partner=payload.get("partner") or session.partner,
            evidence_url=payload.get("evidence_url"),
            event_payload={"source": payload.get("source") or "runtime"},
        )
    except ValueError as exc:
        return _error(str(exc))

    db.session.add(account)
    db.session.add(event)
    record_audit_event(
        db,
        event_type="slash_applied",
        agent_id=agent.id,
        actor_agent_id=actor.id,
        partner=payload.get("partner") or session.partner,
        severity="warning",
        event_payload={"amount": float(amount), "reason": reason},
    )
    db.session.commit()
    return jsonify({"agent": _serialize_agent(agent), "bond_account": serialize_bond_account(account), "event": serialize_bond_event(event)}), 201


@api_bp.post("/agents/<agent_id>/releases")
def publish_agent_release(agent_id: str):
    agent = Agent.query.get_or_404(agent_id)
    payload = request.get_json(silent=True) or {}
    required = ["release_manifest", "signature"]
    missing = [field for field in required if not payload.get(field)]
    if missing:
        return _error(f"Missing required fields: {', '.join(missing)}")

    manifest = payload["release_manifest"]
    provenance_proofs = normalize_provenance_proofs(manifest.get("provenance_proofs") or payload.get("provenance_proofs"))
    if manifest.get("agent_id") != agent.id:
        return _error("Release manifest agent_id does not match target agent.")
    if manifest.get("schema_version") not in {None, RELEASE_SCHEMA_VERSION}:
        return _error("Unsupported release manifest schema version.")
    timestamp_text = manifest.get("timestamp")
    if not timestamp_text:
        return _error("Release manifest requires an ISO timestamp.")
    try:
        manifest_timestamp = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
    except ValueError:
        return _error("Invalid release manifest timestamp.")
    if datetime.now(timezone.utc) - manifest_timestamp > timedelta(hours=24):
        return _error("Release manifest expired. Sign a fresh payload.")
    if not verify_agent_signature(agent.public_key_pem, manifest, payload["signature"]):
        return _error("Invalid release manifest signature.", 401)

    access_token = payload.get("access_token")
    if access_token:
        session = AgentSession.query.filter_by(id=access_token.get("payload", {}).get("session_id")).first()
        if not session_token_is_valid(
            current_app.platform_public_key_pem,
            access_token,
            agent_id=agent.id,
            expected_kind="access",
            required_scope="release:write",
            session=session,
        ):
            return _error("Invalid or expired access token for release publishing.", 401)

    release = AgentRelease(
        agent_id=agent.id,
        version_label=manifest.get("version_label") or manifest.get("release_tag") or "unlabeled",
        repo_url=(manifest.get("repo_url") or "").strip() or None,
        commit_sha=(manifest.get("commit_sha") or "").strip() or None,
        release_tag=(manifest.get("release_tag") or "").strip() or None,
        summary=manifest.get("summary", "").strip(),
        model_version=(manifest.get("model_version") or "").strip() or None,
        runtime_target=(manifest.get("runtime_target") or "").strip() or None,
        capabilities_snapshot=manifest.get("capabilities_snapshot", []),
        major_change=bool(manifest.get("major_change", False)),
        breaking_change=bool(manifest.get("breaking_change", False)),
        schema_version=RELEASE_SCHEMA_VERSION,
        manifest_hash=sha256_text(str(manifest)),
        provenance_proofs=provenance_proofs,
        manifest=manifest,
        manifest_signature=payload["signature"],
    )
    db.session.add(release)
    db.session.flush()
    record_audit_event(
        db,
        event_type="release_published",
        agent_id=agent.id,
        actor_agent_id=agent.id,
        severity="warning" if release.major_change or release.breaking_change else "info",
        event_payload={"release_id": release.id, "version_label": release.version_label, "proof_count": len(provenance_proofs)},
    )
    db.session.commit()
    return jsonify({"release": serialize_release(release), "agent": _serialize_agent(agent)}), 201


@api_bp.get("/releases/recent")
def list_recent_releases():
    releases = AgentRelease.query.order_by(AgentRelease.created_at.desc()).limit(12).all()
    return jsonify({"releases": [serialize_release(item) for item in releases]})


@api_bp.post("/releases/<release_id>/verify")
def verify_release(release_id: str):
    release = AgentRelease.query.get_or_404(release_id)
    payload = request.get_json(silent=True) or {}
    required = ["issuer_agent_id", "verification_claim", "signature"]
    missing = [field for field in required if not payload.get(field)]
    if missing:
        return _error(f"Missing required fields: {', '.join(missing)}")

    issuer = Agent.query.get(payload["issuer_agent_id"])
    if not issuer:
        return _error("Issuer agent not found.", 404)
    if issuer.id == release.agent_id:
        return _error("Agents cannot verify their own release.")

    claim = payload["verification_claim"]
    if claim.get("release_id") != release.id or claim.get("issuer_agent_id") != issuer.id:
        return _error("Verification claim does not match release or issuer.")
    timestamp_text = claim.get("timestamp")
    if not timestamp_text:
        return _error("Verification claim requires an ISO timestamp.")
    try:
        claim_timestamp = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
    except ValueError:
        return _error("Invalid verification claim timestamp.")
    if datetime.now(timezone.utc) - claim_timestamp > timedelta(hours=24):
        return _error("Verification claim expired. Sign a fresh payload.")
    if not verify_agent_signature(issuer.public_key_pem, claim, payload["signature"]):
        return _error("Invalid release verification signature.", 401)

    access_token = payload.get("access_token")
    if access_token:
        session = AgentSession.query.filter_by(id=access_token.get("payload", {}).get("session_id")).first()
        if not session_token_is_valid(
            current_app.platform_public_key_pem,
            access_token,
            agent_id=issuer.id,
            expected_kind="access",
            required_scope="release:verify",
            session=session,
        ):
            return _error("Invalid or expired access token for release verification.", 401)

    verification = ReleaseVerification(
        release_id=release.id,
        issuer_agent_id=issuer.id,
        summary=claim.get("summary", "").strip(),
        confidence=float(claim.get("confidence", payload.get("confidence", 0.8))),
        verification_signature=payload["signature"],
        verification_claim=claim,
    )
    db.session.add(verification)
    db.session.flush()
    record_audit_event(
        db,
        event_type="release_verified",
        agent_id=release.agent_id,
        actor_agent_id=issuer.id,
        severity="info",
        event_payload={"release_id": release.id, "verification_id": verification.id},
    )
    db.session.commit()
    return jsonify({"verification_id": verification.id, "release": serialize_release(release)}), 201


@api_bp.get("/agents/<agent_id>")
def get_agent(agent_id: str):
    agent = Agent.query.get_or_404(agent_id)
    passport = build_agent_passport(
        agent,
        current_app.config["PLATFORM_URL"],
        current_app.platform_signing_key,
        current_app.platform_public_key_pem,
    )
    inbound = (
        Attestation.query.filter_by(subject_agent_id=agent.id)
        .order_by(Attestation.created_at.desc())
        .limit(10)
        .all()
    )
    outbound = (
        Attestation.query.filter_by(issuer_agent_id=agent.id)
        .order_by(Attestation.created_at.desc())
        .limit(10)
        .all()
    )
    return jsonify(
        {
            "agent": _serialize_agent(agent),
            "passport": passport,
            "incoming_attestations": [_serialize_attestation(item) for item in inbound],
            "outgoing_attestations": [_serialize_attestation(item) for item in outbound],
            "eligibility": agent_eligibility(agent),
        }
    )


@api_bp.get("/agents/<agent_id>/passport")
def get_agent_passport(agent_id: str):
    agent = Agent.query.get_or_404(agent_id)
    passport = build_agent_passport(
        agent,
        current_app.config["PLATFORM_URL"],
        current_app.platform_signing_key,
        current_app.platform_public_key_pem,
    )
    return jsonify(passport)


@api_bp.post("/agents/register")
def register_agent():
    payload = request.get_json(silent=True) or {}
    required = ["name", "description", "public_key_pem", "signature", "registration_claim"]
    missing = [field for field in required if not payload.get(field)]
    if missing:
        return _error(f"Missing required fields: {', '.join(missing)}")

    claim = payload["registration_claim"]
    public_key_pem = payload["public_key_pem"]
    signature = payload["signature"]
    fingerprint = fingerprint_public_key(public_key_pem)

    if claim.get("name") != payload["name"] or claim.get("description") != payload["description"]:
        return _error("Signed claim does not match the provided agent identity fields.")

    timestamp_text = claim.get("timestamp")
    if not timestamp_text:
        return _error("Registration claim requires an ISO timestamp.")

    try:
        claim_timestamp = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
    except ValueError:
        return _error("Invalid claim timestamp.")

    if datetime.now(timezone.utc) - claim_timestamp > timedelta(hours=1):
        return _error("Registration claim expired. Please sign a fresh payload.")

    challenge = payload.get("challenge")
    if challenge:
        challenge_payload = challenge.get("payload")
        challenge_signature = challenge.get("platform_signature")
        if not challenge_payload or not challenge_signature:
            return _error("Challenge payload and platform signature are required when challenge is provided.")
        if not verify_platform_signature(current_app.platform_public_key_pem, challenge_payload, challenge_signature):
            return _error("Invalid registration challenge signature.", 401)
        if claim.get("challenge_nonce") != challenge_payload.get("nonce"):
            return _error("Registration claim challenge nonce does not match the platform challenge.")
        try:
            challenge_expiry = datetime.fromisoformat(challenge_payload["expires_at"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            return _error("Invalid registration challenge expiry.")
        if datetime.now(timezone.utc) > challenge_expiry:
            return _error("Registration challenge expired. Request a fresh challenge.")

    if Agent.query.filter_by(public_key_fingerprint=fingerprint).first():
        return _error("This public key is already registered.", 409)

    if not verify_agent_signature(public_key_pem, claim, signature):
        return _error("Invalid agent signature for registration claim.", 401)

    recovery_public_keys = normalize_recovery_public_keys(payload.get("recovery_public_keys"))
    moltbook_token = _trim_text(payload.get("moltbook_identity_token"))
    moltbook_profile = None
    external_proofs = []
    profile_links = {}
    if moltbook_token:
        try:
            moltbook_result = verify_moltbook_identity(
                token=moltbook_token,
                app_key=current_app.config.get("MOLTBOOK_APP_KEY", ""),
                verify_url=current_app.config.get("MOLTBOOK_VERIFY_URL", ""),
            )
        except MoltbookVerificationError as exc:
            return _error(str(exc), 401)

        moltbook_profile = moltbook_result.get("agent") or {}
        owner = moltbook_profile.get("owner") or {}
        external_proofs.append(
            {
                "type": "moltbook_identity",
                "value": str(moltbook_profile.get("id")),
                "status": "verified",
                "proof_url": None,
                "notes": f"karma={moltbook_profile.get('karma', 0)}; verified_status={bool(moltbook_profile.get('is_claimed', False))}",
                "issuer": "moltbook",
                "verified": True,
            }
        )
        if owner.get("x_handle"):
            profile_links["x_handle"] = str(owner["x_handle"])
            profile_links["x_url"] = f"https://x.com/{owner['x_handle']}"

    base_handle = _slugify(payload.get("handle") or payload["name"])
    handle = base_handle
    while Agent.query.filter_by(handle=handle).first():
        handle = f"{base_handle}-{uuid4().hex[:6]}"

    agent = Agent(
        handle=handle,
        name=payload["name"].strip(),
        description=payload["description"].strip(),
        homepage_url=(payload.get("homepage_url") or "").strip() or None,
        capabilities=claim.get("capabilities", []),
        tags=claim.get("tags", []),
        public_key_pem=public_key_pem,
        public_key_fingerprint=fingerprint,
        key_algorithm=payload.get("key_algorithm", "ECDSA_P256_SHA256"),
        identity_version=1,
        active_key_id=fingerprint,
        key_history=[],
        recovery_public_keys=recovery_public_keys,
        owner_signature=signature,
        profile_claim=claim,
        profile_links=profile_links,
        wallet_claims=[],
        external_proofs=external_proofs,
        trust_lenses={},
    )
    db.session.add(agent)
    db.session.commit()
    recalculate_network_scores(db)
    record_audit_event(
        db,
        event_type="agent_registered",
        agent_id=agent.id,
        severity="info",
        event_payload={
            "public_key_fingerprint": fingerprint,
            "identity_version": agent.identity_version,
            "recovery_key_count": len(recovery_public_keys),
            "moltbook_verified": bool(moltbook_profile),
        },
    )
    db.session.commit()

    passport = build_agent_passport(
        agent,
        current_app.config["PLATFORM_URL"],
        current_app.platform_signing_key,
        current_app.platform_public_key_pem,
    )
    return jsonify(
        {
            "agent": _serialize_agent(agent),
            "passport": passport,
            "eligibility": agent_eligibility(agent),
            "next_actions": [
                "Publish your passport to downstream tools and profiles.",
                "Import the saved identity into the dashboard and sign in with partner=dashboard to manage links and wallets.",
                "Collect signed attestations to unlock routing and marketplace access.",
                "Issue attestations to trusted peers to deepen the reputation graph.",
                "Register recovery keys and use signed key rotation when the runtime key changes.",
                "If the agent already has a Moltbook identity token, include it during registration to attach a verified Moltbook proof immediately.",
            ],
        }
    ), 201


@api_bp.post("/attestations")
def create_attestation():
    payload = request.get_json(silent=True) or {}
    required = ["issuer_agent_id", "kind", "summary", "score_delta", "confidence", "signature", "attestation_claim"]
    missing = [field for field in required if payload.get(field) in (None, "")]
    if missing:
        return _error(f"Missing required fields: {', '.join(missing)}")

    issuer = Agent.query.get(payload["issuer_agent_id"])
    subject_agent_id = payload.get("subject_agent_id")
    subject_handle = payload.get("subject_handle")
    subject = Agent.query.get(subject_agent_id) if subject_agent_id else None
    if not subject and subject_handle:
        subject = Agent.query.filter_by(handle=subject_handle).first()
    if not issuer or not subject:
        return _error("Issuer or subject agent not found.", 404)
    if issuer.id == subject.id:
        return _error("Agents cannot attest to themselves.")

    claim = payload["attestation_claim"]
    if claim.get("issuer_agent_id") != issuer.id or claim.get("subject_agent_id") != subject.id:
        return _error("Claim subject/issuer mismatch.")
    if (
        claim.get("kind") != payload["kind"]
        or claim.get("summary") != payload["summary"]
        or float(claim.get("score_delta", 0)) != float(payload["score_delta"])
    ):
        return _error("Signed attestation claim does not match submitted fields.")

    timestamp_text = claim.get("timestamp")
    if not timestamp_text:
        return _error("Attestation claim requires an ISO timestamp.")
    try:
        claim_timestamp = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
    except ValueError:
        return _error("Invalid attestation timestamp.")
    if datetime.now(timezone.utc) - claim_timestamp > timedelta(hours=24):
        return _error("Attestation claim expired. Please sign a fresh payload.")

    if not verify_agent_signature(issuer.public_key_pem, claim, payload["signature"]):
        return _error("Invalid attestation signature.", 401)

    recent_pair_count = Attestation.query.filter(
        Attestation.issuer_agent_id == issuer.id,
        Attestation.subject_agent_id == subject.id,
        Attestation.created_at >= datetime.now(timezone.utc) - timedelta(hours=24),
    ).count()
    if recent_pair_count >= 3:
        return _error("Issuer-to-subject attestation rate limit reached for the last 24 hours.", 429)
    recent_issuer_count = Attestation.query.filter(
        Attestation.issuer_agent_id == issuer.id,
        Attestation.created_at >= datetime.now(timezone.utc) - timedelta(hours=24),
    ).count()
    if recent_issuer_count >= 30:
        return _error("Issuer attestation rate limit reached for the last 24 hours.", 429)

    auth_proof = payload.get("auth_proof")
    access_token = payload.get("access_token")
    authenticated_issuer = False
    if access_token:
        session = AgentSession.query.filter_by(id=access_token.get("payload", {}).get("session_id")).first()
        authenticated_issuer = session_token_is_valid(
            current_app.platform_public_key_pem,
            access_token,
            agent_id=issuer.id,
            expected_kind="access",
            required_scope="attest:write",
            session=session,
        )
        if not authenticated_issuer:
            return _error("Invalid or expired access token for issuer.", 401)
    elif auth_proof:
        authenticated_issuer = auth_proof_is_valid(
            current_app.platform_public_key_pem,
            auth_proof,
            issuer.id,
        )
        if not authenticated_issuer:
            return _error("Invalid or expired auth proof for issuer.", 401)

    evidence_bundle = normalize_evidence_bundle(payload.get("evidence"), fallback_url=(payload.get("evidence_url") or "").strip() or None)
    trust_lenses = claim.get("trust_lenses")
    if not isinstance(trust_lenses, dict):
        trust_lenses = EVENT_LENS_WEIGHTS.get(payload["kind"], {})

    attestation = Attestation(
        issuer_agent_id=issuer.id,
        subject_agent_id=subject.id,
        kind=payload["kind"],
        summary=payload["summary"].strip(),
        evidence_url=(payload.get("evidence_url") or "").strip() or None,
        evidence_hash=(evidence_bundle or {}).get("sha256"),
        evidence_bundle=evidence_bundle,
        interaction_ref=(payload.get("interaction_ref") or "").strip() or None,
        confidence=float(payload["confidence"]),
        score_delta=float(payload["score_delta"]),
        schema_version=ATTESTATION_SCHEMA_VERSION,
        trust_lenses=trust_lenses,
        issuer_credibility=issuer_credibility(issuer),
        issuer_signature=payload["signature"],
        signed_payload=claim,
    )
    db.session.add(attestation)
    db.session.flush()
    record_audit_event(
        db,
        event_type="attestation_created",
        agent_id=subject.id,
        actor_agent_id=issuer.id,
        severity="info",
        event_payload={"attestation_id": attestation.id, "kind": payload["kind"], "authenticated_issuer": authenticated_issuer},
    )
    db.session.commit()
    recalculate_network_scores(db)

    return jsonify({"attestation": _serialize_attestation(attestation), "authenticated_issuer": authenticated_issuer}), 201


@api_bp.get("/attestations")
def list_attestations():
    query = Attestation.query.order_by(Attestation.created_at.desc())
    issuer_agent_id = request.args.get("issuer_agent_id")
    subject_agent_id = request.args.get("subject_agent_id")
    if issuer_agent_id:
        query = query.filter_by(issuer_agent_id=issuer_agent_id)
    if subject_agent_id:
        query = query.filter_by(subject_agent_id=subject_agent_id)
    attestations = query.limit(100).all()
    return jsonify({"attestations": [_serialize_attestation(item) for item in attestations]})


@api_bp.get("/scoreboard")
def scoreboard():
    agents = _sorted_agents_by_effective_score(Agent.query.all())
    return jsonify(
        {
            "scoreboard": [
                {
                    "rank": index + 1,
                    **_serialize_agent(agent),
                }
                for index, agent in enumerate(agents)
            ]
        }
    )


@api_bp.get("/network/graph")
def network_graph():
    agents = Agent.query.order_by(Agent.trust_score.desc()).all()
    attestations = Attestation.query.order_by(Attestation.created_at.desc()).all()
    return jsonify(
        {
            "nodes": [
                {
                    "id": agent.id,
                    "label": agent.name,
                    "handle": agent.handle,
                    "score": agent.trust_score,
                    "attestations": agent.incoming_attestations_count,
                    "tier": agent_eligibility(agent)["access_tier"],
                }
                for agent in agents
            ],
            "edges": [
                {
                    "id": attestation.id,
                    "source": attestation.issuer_agent_id,
                    "target": attestation.subject_agent_id,
                    "kind": attestation.kind,
                    "score_delta": attestation.score_delta,
                    "confidence": attestation.confidence,
                }
                for attestation in attestations
            ],
        }
    )


@api_bp.post("/passports/verify")
def verify_passport():
    payload = request.get_json(silent=True) or {}
    passport_payload = payload.get("payload")
    signature = payload.get("platform_signature")
    public_key_pem = payload.get("platform_public_key")
    if not passport_payload or not signature or not public_key_pem:
        return _error("Passport payload, signature, and platform public key are required.")
    is_valid = public_key_pem.strip() == current_app.platform_public_key_pem.strip() and verify_platform_signature(
        public_key_pem, passport_payload, signature
    )
    return jsonify({"valid": is_valid, "registry": "AgentTrust"})


@api_bp.get("/agents/<agent_id>/eligibility")
def get_agent_eligibility(agent_id: str):
    agent = Agent.query.get_or_404(agent_id)
    return jsonify(agent_eligibility(agent))
