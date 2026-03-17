from __future__ import annotations

from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, send_from_directory


web_bp = Blueprint("web", __name__)


@web_bp.get("/.well-known/agenttrust.json")
def discovery_document():
    base_url = current_app.config["PLATFORM_URL"]
    return jsonify(
        {
            "spec_version": "1.0",
            "service": "AgentTrust",
            "platform_name": "AgentTrust Network",
            "status": "beta",
            "documentation_url": f"{base_url}/",
            "registration_url": f"{base_url}/api/v1/agents/register",
            "registration_quickstart_url": f"{base_url}/api/v1/registration/quickstart",
            "registration_challenge_url": f"{base_url}/api/v1/registration/challenge",
            "auth_challenge_url": f"{base_url}/api/v1/auth/challenge",
            "auth_verify_url": f"{base_url}/api/v1/auth/verify",
            "auth_refresh_url": f"{base_url}/api/v1/auth/refresh",
            "auth_revoke_url": f"{base_url}/api/v1/auth/revoke",
            "registry_url": f"{base_url}/api/v1/agents",
            "resolve_handle_url_template": f"{base_url}/api/v1/agents/resolve/{{handle}}",
            "agent_profile_url_template": f"{base_url}/api/v1/agents/{{agent_id}}/profile",
            "agent_keys_url_template": f"{base_url}/api/v1/agents/{{agent_id}}/keys",
            "key_rotate_url_template": f"{base_url}/api/v1/agents/{{agent_id}}/keys/rotate",
            "key_recover_url_template": f"{base_url}/api/v1/agents/{{agent_id}}/keys/recover",
            "wallet_proof_challenge_url_template": f"{base_url}/api/v1/agents/{{agent_id}}/proofs/wallet/challenge",
            "wallet_proof_verify_url_template": f"{base_url}/api/v1/agents/{{agent_id}}/proofs/wallet/verify",
            "social_proof_start_url_template": f"{base_url}/api/v1/agents/{{agent_id}}/proofs/{{provider}}/start",
            "oauth_callback_url_template": f"{base_url}/api/v1/oauth/{{provider}}/callback",
            "attestation_url": f"{base_url}/api/v1/attestations",
            "release_publish_url_template": f"{base_url}/api/v1/agents/{{agent_id}}/releases",
            "release_verify_url_template": f"{base_url}/api/v1/releases/{{release_id}}/verify",
            "recent_releases_url": f"{base_url}/api/v1/releases/recent",
            "economic_security_url": f"{base_url}/api/v1/economic-security",
            "agent_economic_security_url_template": f"{base_url}/api/v1/agents/{{agent_id}}/economic-security",
            "disputes_url": f"{base_url}/api/v1/disputes",
            "agent_disputes_url_template": f"{base_url}/api/v1/agents/{{agent_id}}/disputes",
            "dispute_review_url_template": f"{base_url}/api/v1/disputes/{{dispute_id}}/reviews",
            "scoreboard_url": f"{base_url}/api/v1/scoreboard",
            "graph_url": f"{base_url}/api/v1/network/graph",
            "network_policy_url": f"{base_url}/api/v1/network/policy",
            "partner_policies_url": f"{base_url}/api/v1/partners/policies",
            "partner_evaluation_url_template": f"{base_url}/api/v1/agents/{{agent_id}}/partner-evaluation/{{partner}}",
            "audit_events_url": f"{base_url}/api/v1/audit/events",
            "ops_metrics_url": f"{base_url}/api/v1/ops/metrics",
            "passport_verification_url": f"{base_url}/api/v1/passports/verify",
            "platform_signature_algorithm": "Ed25519",
            "platform_public_key": current_app.platform_public_key_pem,
            "agent_supported_key_algorithms": ["ECDSA_P256_SHA256", "Ed25519"],
            "capabilities": [
                "self-sovereign-registration",
                "machine-registration-quickstart",
                "registration-challenge",
                "agent-runtime-authentication",
                "owner-dashboard-authentication",
                "signed-agent-passports",
                "versioned-canonical-schemas",
                "key-rotation",
                "key-recovery",
                "agent-attestations",
                "trust-lenses",
                "moltbook-identity-verification",
                "wallet-signature-verification",
                "github-oauth-verification",
                "x-oauth-verification",
                "signed-release-manifests",
                "release-provenance-proofs",
                "release-history",
                "profile-management",
                "external-proof-claims",
                "trust-score-engine",
                "policy-gated-access-tiers",
                "partner-policy-registry",
                "partner-policy-evaluation",
                "anti-sybil-trust-defenses",
                "bond-holdback-slashing",
                "dispute-cases",
                "privacy-preserving-evidence-bundles",
                "reviewer-workflows",
                "audit-log",
                "ops-metrics",
                "discovery-document",
            ],
        }
    )


@web_bp.route("/", defaults={"path": ""})
@web_bp.route("/<path:path>")
def spa(path: str):
    dist_path = Path(current_app.config["FRONTEND_DIST_PATH"])
    target = dist_path / path

    if path and target.exists() and target.is_file():
        if target.suffix == ".md":
            return Response(target.read_text(encoding="utf-8"), mimetype="text/plain")
        return send_from_directory(dist_path, path)

    index = dist_path / "index.html"
    if index.exists():
        return send_from_directory(dist_path, "index.html")

    return jsonify(
        {
            "service": "AgentTrust",
            "message": "Frontend build not found. Run `npm install && npm run build` in /frontend.",
        }
    )
