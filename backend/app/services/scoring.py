from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..models import Agent, Attestation
from .canonical import TRUST_LENS_NAMES, default_trust_lenses
from .economic import MIN_SETTLEMENT_BOND


EVENT_WEIGHTS = {
    "task_completed": 1.2,
    "payment_honored": 1.4,
    "collaboration_success": 1.0,
    "data_accuracy": 1.1,
    "verification_passed": 0.9,
    "incident_report": -1.6,
    "policy_breach": -1.9,
}

EVENT_LENS_WEIGHTS = {
    "task_completed": {"execution": 1.0, "payment": 0.15, "research": 0.15},
    "payment_honored": {"execution": 0.1, "payment": 1.0, "research": 0.0},
    "collaboration_success": {"execution": 0.8, "payment": 0.25, "research": 0.25},
    "data_accuracy": {"execution": 0.2, "payment": 0.0, "research": 1.0},
    "verification_passed": {"execution": 0.4, "payment": 0.15, "research": 0.8},
    "incident_report": {"execution": -0.7, "payment": -0.45, "research": -0.55},
    "policy_breach": {"execution": -0.7, "payment": -0.8, "research": -0.45},
}

OVERALL_LENS_WEIGHTS = {
    "execution": 0.45,
    "payment": 0.35,
    "research": 0.20,
}


def _days_old(created_at: datetime) -> float:
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return max((datetime.now(timezone.utc) - created_at).total_seconds() / 86400, 0.0)


def _recency_multiplier(created_at: datetime) -> float:
    days = _days_old(created_at)
    if days <= 7:
        return 1.0
    if days <= 30:
        return 0.85
    if days <= 90:
        return 0.65
    return 0.45


def _verified_proof_count(agent: Agent) -> int:
    proofs = list(agent.external_proofs or [])
    wallets = list(agent.wallet_claims or [])
    proof_total = len([proof for proof in proofs if proof.get("status") == "verified"])
    wallet_total = len([wallet for wallet in wallets if wallet.get("status") == "verified"])
    return proof_total + wallet_total


def issuer_credibility(agent: Agent) -> float:
    age_days = _days_old(agent.created_at)
    age_multiplier = 0.55 if age_days < 3 else 0.72 if age_days < 14 else 0.92 if age_days < 60 else 1.0
    proof_multiplier = 0.85 + min(_verified_proof_count(agent), 4) * 0.08
    inbound_multiplier = 0.85 + min(int(agent.incoming_attestations_count or 0), 6) * 0.03
    bond_balance = 0.0
    if agent.bond_account:
        bond_balance = float(agent.bond_account.available_balance or 0.0) + float(agent.bond_account.holdback_balance or 0.0)
    bond_multiplier = 0.9 + min(bond_balance / max(MIN_SETTLEMENT_BOND, 1.0), 1.0) * 0.25
    sybil_penalty = max(0.55, 1.0 - (float(agent.sybil_risk_score or 0.0) / 200))
    return max(0.35, min(1.55, age_multiplier * proof_multiplier * inbound_multiplier * bond_multiplier * sybil_penalty))


def _pair_frequency_penalty(attestation: Attestation, recent_pair_count: int) -> float:
    if recent_pair_count <= 1:
        return 1.0
    if recent_pair_count == 2:
        return 0.82
    if recent_pair_count == 3:
        return 0.62
    return 0.42


def _reciprocity_penalty(attestation: Attestation, reciprocal_recent_count: int) -> float:
    if reciprocal_recent_count <= 1:
        return 1.0
    if reciprocal_recent_count == 2:
        return 0.85
    if reciprocal_recent_count == 3:
        return 0.7
    return 0.55


def _lens_base() -> dict[str, float]:
    return default_trust_lenses()


def calculate_agent_lenses(
    agent: Agent,
    attestations: list[Attestation],
    issuer_map: dict[str, Agent],
) -> tuple[dict[str, float], float]:
    lenses = _lens_base()
    now = datetime.now(timezone.utc)

    for attestation in attestations:
        issuer = issuer_map.get(attestation.issuer_agent_id)
        if issuer is None:
            continue
        event_weight = EVENT_WEIGHTS.get(attestation.kind, 1.0)
        credibility = issuer_credibility(issuer)
        pair_recent_count = Attestation.query.filter(
            Attestation.issuer_agent_id == attestation.issuer_agent_id,
            Attestation.subject_agent_id == attestation.subject_agent_id,
            Attestation.created_at >= now - timedelta(days=30),
        ).count()
        reciprocal_recent_count = Attestation.query.filter(
            Attestation.issuer_agent_id == attestation.subject_agent_id,
            Attestation.subject_agent_id == attestation.issuer_agent_id,
            Attestation.created_at >= now - timedelta(days=30),
        ).count()
        pair_penalty = _pair_frequency_penalty(attestation, pair_recent_count)
        reciprocity_penalty = _reciprocity_penalty(attestation, reciprocal_recent_count)
        confidence = max(0.1, min(float(attestation.confidence or 0.0), 1.0))
        recency = _recency_multiplier(attestation.created_at)
        impact = (
            float(attestation.score_delta)
            * event_weight
            * credibility
            * confidence
            * recency
            * pair_penalty
            * reciprocity_penalty
        )
        lens_weights = EVENT_LENS_WEIGHTS.get(attestation.kind, {"execution": 0.55, "payment": 0.2, "research": 0.25})
        for lens in TRUST_LENS_NAMES:
            lenses[lens] += impact * lens_weights.get(lens, 0.0) * 18

    for lens in TRUST_LENS_NAMES:
        lenses[lens] = round(max(0.0, min(100.0, lenses[lens])), 2)

    overall = sum(lenses[lens] * OVERALL_LENS_WEIGHTS[lens] for lens in TRUST_LENS_NAMES)
    return lenses, round(max(0.0, min(100.0, overall)), 2)


def calculate_sybil_risk(agent: Agent, inbound: list[Attestation], outbound: int) -> float:
    age_days = _days_old(agent.created_at)
    verified_proofs = _verified_proof_count(agent)
    low_age_risk = 28 if age_days < 7 else 14 if age_days < 30 else 4
    proof_risk = 16 if verified_proofs == 0 else 6 if verified_proofs == 1 else 0
    outbound_risk = min(outbound * 3.5, 24)
    reciprocal_sources = {item.issuer_agent_id for item in inbound[:10]}
    concentration_risk = 18 if inbound and len(reciprocal_sources) <= 1 else 10 if inbound and len(reciprocal_sources) <= 2 else 0
    bond_balance = 0.0
    if agent.bond_account:
        bond_balance = float(agent.bond_account.available_balance or 0.0) + float(agent.bond_account.holdback_balance or 0.0)
    bond_relief = min((bond_balance / max(MIN_SETTLEMENT_BOND, 1.0)) * 18, 18)
    incoming_relief = min(len(inbound) * 2, 12)
    risk = low_age_risk + proof_risk + outbound_risk + concentration_risk - bond_relief - incoming_relief
    return round(max(0.0, min(100.0, risk)), 2)


def recalculate_network_scores(db) -> None:
    agents = Agent.query.order_by(Agent.created_at.asc()).all()
    issuer_map = {agent.id: agent for agent in agents}

    for _ in range(3):
        for agent in agents:
            inbound = (
                Attestation.query.filter_by(subject_agent_id=agent.id)
                .order_by(Attestation.created_at.desc())
                .all()
            )
            outbound = Attestation.query.filter_by(issuer_agent_id=agent.id).count()
            trust_lenses, overall = calculate_agent_lenses(agent, inbound, issuer_map)
            agent.trust_lenses = trust_lenses
            agent.trust_score = overall
            agent.incoming_attestations_count = len(inbound)
            agent.outgoing_attestations_count = outbound
            agent.sybil_risk_score = calculate_sybil_risk(agent, inbound, outbound)
            issuer_map[agent.id] = agent

    db.session.commit()
