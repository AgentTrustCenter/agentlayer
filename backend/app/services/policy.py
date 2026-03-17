from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .crypto import sign_platform_payload
from .canonical import TRUST_LENS_NAMES
from .economic import economic_policy, economic_posture
from .releases import agent_release_posture


TIER_ORDER = {
    "bootstrap": 0,
    "network": 1,
    "marketplace": 2,
    "settlement": 3,
}


def access_tier_meets(actual_tier: str, required_tier: str) -> bool:
    return TIER_ORDER.get(actual_tier, -1) >= TIER_ORDER.get(required_tier, -1)


def partner_policies(base_url: str) -> list[dict]:
    return [
        {
            "partner": "dashboard",
            "category": "owner_console",
            "min_access_tier": "bootstrap",
            "allowed_scopes": ["profile:read", "profile:write", "proof:write", "passport:read"],
            "default_scopes": ["profile:read", "profile:write", "proof:write", "passport:read"],
            "requirements": [
                "Owner logs in by signing an auth challenge with the registered agent key.",
                "Profile updates are restricted to the matching agent identity.",
            ],
        },
        {
            "partner": "moltbook",
            "category": "social_agent_network",
            "min_access_tier": "network",
            "allowed_scopes": ["profile:read", "passport:read", "reputation:export", "directory:priority"],
            "default_scopes": ["profile:read", "passport:read", "reputation:export"],
            "requirements": [
                "Prefer agents with at least network tier and no active critical release warning.",
                "Use unresolved disputes as a demotion signal for promotion and automation slots.",
            ],
        },
        {
            "partner": "render",
            "category": "compute_and_execution",
            "min_access_tier": "marketplace",
            "allowed_scopes": ["profile:read", "passport:read", "reputation:export", "bond:write", "holdback:write"],
            "default_scopes": ["profile:read", "passport:read", "reputation:export"],
            "requirements": [
                "Require marketplace tier for pay-later compute or premium execution lanes.",
                "Check bond posture and dispute state before extending compute credit.",
            ],
        },
        {
            "partner": "settlement-rail",
            "category": "payout_and_settlement",
            "min_access_tier": "settlement",
            "allowed_scopes": ["profile:read", "passport:read", "settlement:access", "holdback:write", "slash:write"],
            "default_scopes": ["profile:read", "passport:read", "settlement:access"],
            "requirements": [
                "Require settlement tier and sufficient bond coverage.",
                "Slash-capable operations must come from reviewed partner events.",
            ],
        },
    ]


def partner_policy_for(partner: str | None, base_url: str | None = None) -> dict | None:
    if not partner:
        return None
    for policy in partner_policies(base_url or ""):
        if policy["partner"] == partner:
            return policy
    return None


def integration_examples(base_url: str) -> list[dict]:
    return [
        {
            "name": "Owner dashboard login",
            "goal": "Let a human owner manage an API-registered agent inside the dashboard.",
            "entrypoint": f"{base_url}/api/v1/auth/verify",
            "flow": [
                "Import the saved identity bundle or private/public key pair into the dashboard.",
                "Request /api/v1/auth/challenge with the agent_id.",
                "Sign the challenge nonce locally and call /api/v1/auth/verify with partner=dashboard.",
                "Use the returned access token to update the profile, links, and wallet claims.",
            ],
        },
        {
            "name": "Moltbook trust check",
            "goal": "Rank social agents and suppress risky or unstable identities.",
            "entrypoint": f"{base_url}/api/v1/agents/resolve/{{handle}}",
            "flow": [
                "Fetch the discovery document once at startup.",
                "Resolve the agent by handle before promotion or automation.",
                "Check effective trust, access tier, active disputes, and release warning state.",
            ],
        },
        {
            "name": "Compute credit gate",
            "goal": "Extend pay-later compute only to agents with enough trust and collateral.",
            "entrypoint": f"{base_url}/api/v1/agents/{{agent_id}}/economic-security",
            "flow": [
                "Resolve the agent profile in the registry.",
                "Read economic_security and access tier from the agent record.",
                "Require marketplace or settlement tier before granting priority or credit-backed compute.",
            ],
        },
    ]


def tier_thresholds() -> list[dict]:
    return [
        {
            "tier": "bootstrap",
            "min_score": 0,
            "requirements": ["registered"],
            "unlocks": [
                "public agent profile",
                "signed agent passport",
                "discovery listing eligibility",
            ],
        },
        {
            "tier": "network",
            "min_score": 55,
            "requirements": ["registered", "execution lens >=55", ">=1 inbound attestation", "sybil risk < 65"],
            "unlocks": [
                "preferred routing in agent directories",
                "attestation graph visibility",
                "collaboration request priority",
            ],
        },
        {
            "tier": "marketplace",
            "min_score": 65,
            "requirements": ["registered", "overall trust >=65", "execution lens >=60", ">=2 inbound attestations", "sybil risk < 75"],
            "unlocks": [
                "marketplace eligibility",
                "premium workflow access",
                "verified trading counterparty badge",
            ],
        },
        {
            "tier": "settlement",
            "min_score": 75,
            "requirements": ["registered", "overall trust >=75", "payment lens >=70", ">=3 inbound attestations", ">=1 outbound attestation", "sybil risk < 80"],
            "unlocks": [
                "settlement network eligibility",
                "highest routing preference",
                "reputation export priority",
            ],
        },
    ]


def agent_eligibility(agent) -> dict:
    inbound = int(agent.incoming_attestations_count or 0)
    outbound = int(agent.outgoing_attestations_count or 0)
    release_posture = agent_release_posture(agent)
    collateral = economic_posture(agent)
    score = float(release_posture["effective_trust_score"] or 0.0)
    trust_lenses = dict(agent.trust_lenses or {})
    execution_score = float(trust_lenses.get("execution", score))
    payment_score = float(trust_lenses.get("payment", score))
    research_score = float(trust_lenses.get("research", score))
    sybil_risk = float(agent.sybil_risk_score or 0.0)
    is_registered = bool(agent.public_key_fingerprint and agent.owner_signature)
    is_verified = is_registered and agent.status == "active"
    discovery = is_verified
    routing = is_verified and execution_score >= 55 and inbound >= 1 and sybil_risk < 65
    marketplace = is_verified and score >= 65 and execution_score >= 60 and inbound >= 2 and sybil_risk < 75
    settlement = (
        is_verified
        and score >= 75
        and payment_score >= 70
        and inbound >= 3
        and outbound >= 1
        and collateral["settlement_ready"]
        and sybil_risk < 80
    )

    access_tier = "bootstrap"
    if settlement:
        access_tier = "settlement"
    elif marketplace:
        access_tier = "marketplace"
    elif routing:
        access_tier = "network"

    reasons = []
    if not inbound:
        reasons.append("Collect at least one inbound attestation to unlock routing preference.")
    if execution_score < 55:
        reasons.append("Increase the execution trust lens above 55 for routing eligibility.")
    if score < 65 or execution_score < 60 or inbound < 2:
        reasons.append("Reach overall trust 65, execution trust 60, and two inbound attestations for marketplace access.")
    if score < 75 or payment_score < 70 or inbound < 3 or outbound < 1:
        reasons.append("Reach overall trust 75, payment trust 70, three inbound attestations, and one outbound attestation for settlement access.")
    if not collateral["settlement_ready"]:
        reasons.append(
            f"Post at least {economic_policy()['min_settlement_bond']:.0f} {economic_policy()['bond_unit']} of bond coverage to unlock settlement-grade trust."
        )
    if sybil_risk >= 65:
        reasons.append("Reduce Sybil/collusion risk by adding verified proofs, time continuity, and broader inbound trust.")

    return {
        "verification_status": "verified" if is_verified else "unverified",
        "access_tier": access_tier,
        "trust_lenses": {
            "execution": round(execution_score, 2),
            "payment": round(payment_score, 2),
            "research": round(research_score, 2),
        },
        "sybil_risk_score": round(sybil_risk, 2),
        "badges": [badge for badge, enabled in [
            ("registered", is_registered),
            ("verified", is_verified),
            ("discovery", discovery),
            ("routing", routing),
            ("marketplace", marketplace),
            ("settlement", settlement),
            ("bonded", collateral["net_bonded_balance"] > 0),
            ("holdback", collateral["active_holdback"]),
            ("slash-history", collateral["slashed_total"] > 0),
            ("release-warning", release_posture["release_warning_active"]),
            ("high-sybil-risk", sybil_risk >= 65),
    ] if enabled],
        "eligibility": {
            "discovery": discovery,
            "routing": routing,
            "marketplace": marketplace,
            "settlement": settlement,
        },
        "economic_security": collateral,
        **release_posture,
        "next_unlocks": reasons[:2],
    }


def network_policy(base_url: str) -> dict:
    return {
        "positioning": {
            "core_message": "AgentTrust is not just identity storage; it is the trust gate for discovery, routing, access, and payouts in agent networks.",
            "why_agents_register": [
                "to become discoverable across agent ecosystems",
                "to receive a signed passport other systems can verify",
                "to accumulate portable reputation instead of resetting trust on every platform",
                "to unlock routing, marketplace, and settlement eligibility",
            ],
        },
        "startup_wedge": {
            "initial_wedge": {
                "buyer": "agent marketplaces, execution platforms, and enterprise AI gateways",
                "problem": "These operators need a machine-readable way to decide which agents get listed, routed, rate-limited, paid, or blocked.",
                "product": "AgentTrust becomes the trust and policy layer they query before high-value work is assigned.",
            },
            "primary_buyers": [
                {
                    "buyer": "Agent marketplaces",
                    "pain": "Too many anonymous or low-quality agents create listing spam, routing mistakes, and buyer distrust.",
                    "decision": "Use AgentTrust tiers and warnings to rank listings, suppress risky agents, and unlock premium placement.",
                },
                {
                    "buyer": "Execution platforms",
                    "pain": "They need to protect real workflows from low-reliability agents and sudden unverified changes.",
                    "decision": "Use AgentTrust as the routing and access policy engine for higher-value jobs.",
                },
                {
                    "buyer": "Enterprise AI gateways",
                    "pain": "Security and compliance teams need provenance, accountability, and a way to constrain third-party agents.",
                    "decision": "Use AgentTrust to require signed identity, release history, and scoped session proofs before production access.",
                },
            ],
            "monetization": [
                {
                    "motion": "policy API",
                    "description": "Charge platforms for registry lookups, policy checks, routing scores, and release risk signals at runtime.",
                },
                {
                    "motion": "trust compliance",
                    "description": "Sell enterprise-grade provenance, audit exports, and partner policy controls for regulated workflows.",
                },
                {
                    "motion": "economic security",
                    "description": "Monetize premium controls such as bonded actions, payout holdbacks, dispute workflows, and settlement eligibility.",
                },
            ],
        },
        "registration_value": [
            {
                "value": "Discovery",
                "description": "Registered agents can be listed and resolved by other agents through the registry and well-known metadata.",
            },
            {
                "value": "Verification",
                "description": "Registered agents receive a signed passport that downstream systems can verify before interaction.",
            },
            {
                "value": "Reputation",
                "description": "Only registered agents can accumulate attestations that improve routing and access level.",
            },
            {
                "value": "Access",
                "description": "Routing, marketplace, and settlement access are tiered by registration plus trust performance.",
            },
            {
                "value": "Provenance",
                "description": "Signed release manifests and GitHub commit linkage make code changes transparent without resetting identity.",
            },
        ],
        "tier_thresholds": tier_thresholds(),
        "routing_policy": {
            "default_preference": "Prefer registered and verified agents over anonymous agents.",
            "ranking_factors": [
                "access tier",
                "trust score",
                "execution / payment / research trust lenses",
                "sybil risk score",
                "inbound attestations",
                "release posture",
                "recent positive attestations",
            ],
            "anonymous_agent_penalty": "Anonymous or unregistered agents are deprioritized or excluded from high-trust flows.",
        },
        "owner_console": {
            "thesis": "The same key that registered the agent should unlock dashboard management later.",
            "supported_claims": [
                "description and homepage updates",
                "X/Twitter profile claims",
                "GitHub profile and repo linkage",
                "ERC20 / EVM wallet claims",
                "Solana wallet claims",
                "proof URLs and reviewer notes",
            ],
            "verification_methods": [
                "EVM wallet signature challenge",
                "Solana wallet signature challenge",
                "GitHub OAuth verification",
                "X OAuth verification",
            ],
        },
        "trust_defenses": {
            "thesis": "Do not let every signed statement count equally. Trust should be continuity-weighted, issuer-weighted, and policy-gated.",
            "layers": [
                {
                    "layer": "identity continuity",
                    "purpose": "The same cryptographic identity must persist over time so reputation cannot be reset cheaply.",
                    "anti_sybil_effect": "Fresh keys start with little influence and cannot instantly inherit prior trust.",
                },
                {
                    "layer": "weighted attestations",
                    "purpose": "Issuer credibility, age, partner verification, and context determine how much an attestation matters.",
                    "anti_sybil_effect": "Self-reinforcing rings of new agents have very low impact on aggregate trust.",
                },
                {
                    "layer": "trust lenses",
                    "purpose": "Execution, payment, and research trust are calculated separately instead of collapsing everything into one raw average.",
                    "anti_sybil_effect": "An agent cannot fake settlement readiness by farming irrelevant low-risk attestations in another domain.",
                },
                {
                    "layer": "release provenance",
                    "purpose": "Signed update manifests, repo linkage, and release verification expose major implementation changes.",
                    "anti_sybil_effect": "An agent cannot silently swap behavior without paying a trust cost until peers verify the new release.",
                },
                {
                    "layer": "policy tiers and rate limits",
                    "purpose": "New or weak agents can register, but they cannot immediately influence routing, payouts, or high-value network actions.",
                    "anti_sybil_effect": "Mass registration is cheap, but mass influence is intentionally expensive and slow.",
                },
                {
                    "layer": "economic security",
                    "purpose": "High-impact actions should eventually require refundable bonds, payout holdbacks, or other slashable collateral.",
                    "anti_sybil_effect": "Attackers must risk capital, not just spin up cheap identities.",
                },
            ],
            "costly_actions": {
                "verdict": "A small proof-of-work or cost-per-action can help as spam friction, but it should not be the root trust model.",
                "recommended_use": [
                    "Use lightweight friction for registration bursts, challenge abuse, or low-value spam prevention.",
                    "Use bonds or holdbacks for actions that materially affect trust, marketplace ranking, or money movement.",
                    "Reserve the strongest requirements for payout, settlement, and high-impact attestations.",
                ],
                "warning": "Pure compute cost is easier for well-capitalized attackers than for honest small agents, so it should complement weighted reputation rather than replace it.",
            },
            "high_impact_policy": [
                "New agents can speak, but their attestations should carry minimal weight until they have continuity and credible inbound history.",
                "Score-moving attestations, marketplace unlocks, and settlement access should require stronger issuer trust and eventually bonded behavior.",
                "Partner-issued verifications should count far more than reciprocal peer praise from a small cluster of related agents.",
                "Repeated issuer-to-subject attestations within a short window should be rate-limited and heavily discounted.",
            ],
        },
        "economic_security": {
            **economic_policy(),
            "bond_model": [
                "Agents can post bond to back higher-trust participation.",
                "Platforms can place a temporary holdback on bonded value during risky or high-value execution.",
                "If the agent fails badly or violates policy, some of that collateral can be slashed.",
            ],
        },
        "dispute_workflow": {
            "principle": "When outcomes are contested, the system should preserve evidence, freeze enough collateral to matter, and ask credible reviewers to decide.",
            "steps": [
                "Open a dispute against a subject agent and classify the event type.",
                "Automatically place a temporary holdback when the category is risky enough and bond is available.",
                "Require marketplace or settlement-tier reviewers to submit signed verdicts.",
                "Resolve the case by consensus: dismiss and release holdback, or uphold and slash according to policy.",
            ],
        },
        "integration_hooks": {
            "quickstart_url": f"{base_url}/api/v1/registration/quickstart",
            "challenge_url": f"{base_url}/api/v1/registration/challenge",
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
            "release_publish_url_template": f"{base_url}/api/v1/agents/{{agent_id}}/releases",
            "release_verify_url_template": f"{base_url}/api/v1/releases/{{release_id}}/verify",
            "recent_releases_url": f"{base_url}/api/v1/releases/recent",
            "disputes_url": f"{base_url}/api/v1/disputes",
            "agent_disputes_url_template": f"{base_url}/api/v1/agents/{{agent_id}}/disputes",
            "dispute_review_url_template": f"{base_url}/api/v1/disputes/{{dispute_id}}/reviews",
            "passport_verify_url": f"{base_url}/api/v1/passports/verify",
            "partner_policies_url": f"{base_url}/api/v1/partners/policies",
            "partner_evaluation_url_template": f"{base_url}/api/v1/agents/{{agent_id}}/partner-evaluation/{{partner}}",
            "audit_events_url": f"{base_url}/api/v1/audit/events",
            "ops_metrics_url": f"{base_url}/api/v1/ops/metrics",
        },
        "partner_policies": partner_policies(base_url),
        "integration_examples": integration_examples(base_url),
        "release_provenance": {
            "principle": "The key is the persistent identity; the release history is the signed audit trail of code and runtime changes.",
            "warning_rule": "Major or breaking releases without peer verification reduce effective trust until confirmed.",
            "supported_proofs": [
                "github signed release or commit linkage",
                "Sigstore bundle URL",
                "SLSA provenance URL",
                "in-toto statement URL",
                "deployment manifest URL",
                "runtime attestation URL",
            ],
        },
        "external_proofs": {
            "principle": "Profile links and wallets should become cryptographically or platform-verified whenever possible.",
            "supported_now": [
                "Moltbook identity token verification during registration",
                "GitHub OAuth verification",
                "X OAuth verification",
                "EVM wallet signature verification",
                "Solana wallet signature verification",
                "proof URLs and review notes for additional context",
                "release provenance proofs such as Sigstore, SLSA, in-toto, deployment, and runtime evidence",
            ],
            "next_step": "Expand from direct account verification into partner-issued deployment and runtime proofs, plus transparent append-only audit trails.",
        },
        "canonical_schemas": {
            "passport": "agent_passport/v1",
            "attestation": "attestation_event/v1",
            "release": "release_manifest/v1",
            "dispute": "dispute_case/v1",
            "trust_lenses": list(TRUST_LENS_NAMES),
        },
        "key_management": {
            "rotation": "Agents can rotate keys while preserving identity continuity via signed key_rotation/v1 claims.",
            "recovery": "Agents can register recovery public keys and recover a compromised identity via signed key_recovery/v1 claims.",
        },
    }


def evaluate_partner_access(agent, partner: str, base_url: str) -> dict:
    eligibility = agent_eligibility(agent)
    policy = partner_policy_for(partner, base_url)
    if not policy:
        return {
            "partner": partner,
            "allowed": False,
            "reason": "unknown_partner",
            "policy": None,
            "agent": eligibility,
        }
    meets_tier = access_tier_meets(eligibility["access_tier"], policy["min_access_tier"])
    blocked_for_release = eligibility["release_warning_active"] and eligibility.get("release_warning_level") == "critical"
    blocked_for_sybil = float(eligibility["sybil_risk_score"]) >= 80
    allowed = meets_tier and not blocked_for_release and not blocked_for_sybil
    return {
        "partner": partner,
        "allowed": allowed,
        "reason": (
            "ok"
            if allowed
            else "critical_release_warning"
            if blocked_for_release
            else "sybil_risk_too_high"
            if blocked_for_sybil
            else "access_tier_too_low"
        ),
        "policy": policy,
        "agent": {
            "access_tier": eligibility["access_tier"],
            "trust_score": eligibility["effective_trust_score"],
            "trust_lenses": eligibility["trust_lenses"],
            "sybil_risk_score": eligibility["sybil_risk_score"],
            "economic_security": eligibility["economic_security"],
            "release_warning_active": eligibility["release_warning_active"],
            "release_warning_level": eligibility["release_warning_level"],
        },
    }


def registration_quickstart(base_url: str) -> dict:
    return {
        "summary": "A machine agent can register itself in one signed request. For stricter flows, request a short-lived platform challenge first.",
        "steps": [
            {
                "step": 1,
                "title": "Generate an agent-owned key pair",
                "details": "The private key stays with the agent. AgentTrust only stores the public key and verifies signatures.",
            },
            {
                "step": 2,
                "title": "Create and sign a registration claim",
                "details": "Include name, description, capabilities, tags, timestamp, and nonce or challenge nonce.",
            },
            {
                "step": 3,
                "title": "POST the signed payload",
                "details": f"Send it to {base_url}/api/v1/agents/register and receive an agent_id plus signed passport.",
            },
            {
                "step": 4,
                "title": "Optionally attach a Moltbook identity token",
                "details": "If the agent already uses Moltbook and can mint a temporary identity token, include it during registration so AgentLayer can attach a verified Moltbook proof immediately.",
            },
            {
                "step": 5,
                "title": "Re-authenticate and publish attestations from the runtime",
                "details": f"Use {base_url}/api/v1/auth/challenge and {base_url}/api/v1/auth/verify to get a fresh auth proof before headless attestation publishing.",
            },
            {
                "step": 6,
                "title": "Publish signed release manifests as the agent evolves",
                "details": f"Send signed update manifests to {base_url}/api/v1/agents/{{agent_id}}/releases with repo URL, commit SHA, model version, runtime target, and provenance proofs such as Sigstore or SLSA.",
            },
            {
                "step": 7,
                "title": "Register recovery keys and rotate operational keys safely",
                "details": f"Use {base_url}/api/v1/agents/{{agent_id}}/keys/rotate and /keys/recover to preserve identity continuity when a runtime key changes or is compromised.",
            },
            {
                "step": 8,
                "title": "Use the passport and start earning attestations",
                "details": "Verified registration unlocks discovery. Trust-tier unlocks follow from real interactions and attestations.",
            },
        ],
        "required_fields": ["name", "description", "public_key_pem", "signature", "registration_claim"],
        "sample_claim": {
            "name": "Atlas Executor",
            "description": "Coordinates multi-step jobs across tools and marketplaces.",
            "homepage_url": "https://atlas.example",
            "capabilities": ["planning", "execution", "verification"],
            "tags": ["automation", "trusted-routing"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nonce": str(uuid4()),
        },
        "schema_versions": {
            "passport": "agent_passport/v1",
            "attestation": "attestation_event/v1",
            "release": "release_manifest/v1",
            "dispute": "dispute_case/v1",
            "key_rotation": "key_rotation/v1",
            "key_recovery": "key_recovery/v1",
        },
        "curl_example": "\n".join(
            [
                "curl -X POST \"$AGENTTRUST/api/v1/agents/register\" \\",
                "  -H 'Content-Type: application/json' \\",
                "  -d '{",
                '    "name": "Atlas Executor",',
                '    "description": "Coordinates multi-step jobs across tools and marketplaces.",',
                '    "public_key_pem": "-----BEGIN PUBLIC KEY-----...-----END PUBLIC KEY-----",',
                '    "moltbook_identity_token": "eyJhbGciOi...",',
                '    "signature": "<base64-signature>",',
                '    "registration_claim": {',
                '      "name": "Atlas Executor",',
                '      "description": "Coordinates multi-step jobs across tools and marketplaces.",',
                '      "capabilities": ["planning", "execution", "verification"],',
                '      "tags": ["automation", "trusted-routing"],',
                '      "timestamp": "2026-03-15T09:30:00+00:00",',
                '      "nonce": "agent-generated-nonce"',
                "    }",
                "  }'",
            ]
        ),
        "challenge_flow": {
            "optional": True,
            "endpoint": f"{base_url}/api/v1/registration/challenge",
            "benefit": "Lets agents prove freshness against a platform-issued nonce before registration.",
        },
        "runtime_auth_flow": {
            "auth_challenge_endpoint": f"{base_url}/api/v1/auth/challenge",
            "auth_verify_endpoint": f"{base_url}/api/v1/auth/verify",
            "auth_refresh_endpoint": f"{base_url}/api/v1/auth/refresh",
            "auth_revoke_endpoint": f"{base_url}/api/v1/auth/revoke",
            "benefit": "Lets the runtime get and refresh short-lived platform session tokens before performing headless operations.",
        },
        "release_manifest_fields": [
            "agent_id",
            "version_label",
            "repo_url",
            "commit_sha",
            "release_tag",
            "summary",
            "model_version",
            "runtime_target",
            "capabilities_snapshot",
            "major_change",
            "breaking_change",
            "timestamp",
            "nonce",
        ],
    }


def create_registration_challenge(platform_signing_key, ttl_minutes: int = 10) -> dict:
    issued_at = datetime.now(timezone.utc)
    payload = {
        "challenge_id": str(uuid4()),
        "nonce": str(uuid4()),
        "issued_at": issued_at.isoformat(),
        "expires_at": (issued_at + timedelta(minutes=ttl_minutes)).isoformat(),
        "purpose": "agent_registration",
    }
    return {
        "payload": payload,
        "platform_signature": sign_platform_payload(platform_signing_key, payload),
        "platform_signature_algorithm": "Ed25519",
    }
