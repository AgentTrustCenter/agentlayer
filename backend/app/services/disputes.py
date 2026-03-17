from __future__ import annotations

from datetime import datetime, timezone

from .economic import record_bond_event, serialize_bond_event
from .canonical import DISPUTE_SCHEMA_VERSION


DISPUTE_RULES = {
    "settlement_failure": {
        "severity": "high",
        "holdback_ratio": 0.25,
        "slash_ratio": 0.2,
        "min_holdback": 5.0,
        "reviewer_threshold": 2,
    },
    "policy_breach": {
        "severity": "critical",
        "holdback_ratio": 0.35,
        "slash_ratio": 0.3,
        "min_holdback": 8.0,
        "reviewer_threshold": 2,
    },
    "fraud_signal": {
        "severity": "critical",
        "holdback_ratio": 0.5,
        "slash_ratio": 0.45,
        "min_holdback": 10.0,
        "reviewer_threshold": 2,
    },
    "release_mismatch": {
        "severity": "medium",
        "holdback_ratio": 0.1,
        "slash_ratio": 0.08,
        "min_holdback": 2.0,
        "reviewer_threshold": 2,
    },
    "quality_failure": {
        "severity": "medium",
        "holdback_ratio": 0.15,
        "slash_ratio": 0.1,
        "min_holdback": 3.0,
        "reviewer_threshold": 2,
    },
}


def dispute_rules() -> dict:
    return DISPUTE_RULES


def dispute_rule_for_category(category: str) -> dict:
    return DISPUTE_RULES.get(
        category,
        {
            "severity": "medium",
            "holdback_ratio": 0.12,
            "slash_ratio": 0.08,
            "min_holdback": 2.0,
            "reviewer_threshold": 2,
        },
    )


def recommended_holdback_amount(agent, category: str) -> float:
    account = agent.bond_account
    available = float(account.available_balance if account else 0.0)
    if available <= 0:
        return 0.0
    rule = dispute_rule_for_category(category)
    proposed = max(rule["min_holdback"], available * rule["holdback_ratio"])
    return round(min(available, proposed), 2)


def recommended_slash_amount(agent, category: str) -> float:
    account = agent.bond_account
    total_covered = 0.0
    if account:
        total_covered = float(account.available_balance or 0.0) + float(account.holdback_balance or 0.0)
    if total_covered <= 0:
        return 0.0
    rule = dispute_rule_for_category(category)
    proposed = total_covered * rule["slash_ratio"]
    return round(min(total_covered, max(1.0, proposed)), 2)


def serialize_dispute_review(review) -> dict:
    return {
        "id": review.id,
        "dispute_id": review.dispute_id,
        "reviewer_agent_id": review.reviewer_agent_id,
        "verdict": review.verdict,
        "summary": review.summary,
        "recommended_slash_amount": round(float(review.recommended_slash_amount or 0.0), 2),
        "created_at": review.created_at.isoformat(),
    }


def serialize_dispute_case(dispute) -> dict:
    return {
        "schema_version": dispute.schema_version or DISPUTE_SCHEMA_VERSION,
        "id": dispute.id,
        "subject_agent_id": dispute.subject_agent_id,
        "opened_by_agent_id": dispute.opened_by_agent_id,
        "category": dispute.category,
        "severity": dispute.severity,
        "title": dispute.title,
        "summary": dispute.summary,
        "evidence_url": dispute.evidence_url,
        "evidence_hash": dispute.evidence_hash,
        "evidence_bundle": dispute.evidence_bundle or {},
        "privacy_redaction": dispute.privacy_redaction,
        "status": dispute.status,
        "auto_holdback_amount": round(float(dispute.auto_holdback_amount or 0.0), 2),
        "recommended_slash_amount": round(float(dispute.recommended_slash_amount or 0.0), 2),
        "resolution": dispute.resolution,
        "resolution_summary": dispute.resolution_summary,
        "created_at": dispute.created_at.isoformat(),
        "resolved_at": dispute.resolved_at.isoformat() if dispute.resolved_at else None,
        "related_attestation_id": dispute.related_attestation_id,
        "related_release_id": dispute.related_release_id,
        "review_count": len(dispute.reviews),
        "reviews": [serialize_dispute_review(review) for review in sorted(dispute.reviews, key=lambda item: item.created_at, reverse=True)],
        "resolution_event": serialize_bond_event(dispute.resolution_event) if dispute.resolution_event else None,
    }


def apply_opening_holdback(dispute, opener_agent_id: str | None = None):
    if dispute.auto_holdback_amount <= 0:
        return None, None
    account, event = record_bond_event(
        dispute.subject,
        event_type="holdback_locked",
        amount=dispute.auto_holdback_amount,
        reason=f"Automatic holdback for dispute {dispute.category}: {dispute.title}",
        actor_agent_id=opener_agent_id,
        evidence_url=dispute.evidence_url,
        event_payload={"dispute_id": dispute.id, "category": dispute.category, "phase": "opened"},
    )
    return account, event


def maybe_resolve_dispute(dispute):
    reviews = list(dispute.reviews)
    rule = dispute_rule_for_category(dispute.category)
    threshold = int(rule["reviewer_threshold"])
    uphold_count = len([review for review in reviews if review.verdict == "uphold"])
    dismiss_count = len([review for review in reviews if review.verdict == "dismiss"])

    if dispute.status != "open":
        return None

    if uphold_count >= threshold:
        slash_amount = round(
            max(
                float(dispute.recommended_slash_amount or 0.0),
                max((float(review.recommended_slash_amount or 0.0) for review in reviews if review.verdict == "uphold"), default=0.0),
            ),
            2,
        )
        slash_amount = max(0.0, slash_amount)
        resolution_event = None
        account = None
        if slash_amount > 0:
            account, resolution_event = record_bond_event(
                dispute.subject,
                event_type="slash_applied",
                amount=slash_amount,
                reason=f"Reviewer consensus upheld dispute {dispute.id}: {dispute.title}",
                evidence_url=dispute.evidence_url,
                event_payload={"dispute_id": dispute.id, "category": dispute.category, "phase": "resolution"},
            )
        dispute.status = "resolved"
        dispute.resolution = "slashed" if resolution_event else "upheld"
        dispute.resolution_summary = "Reviewer consensus upheld the dispute and applied the configured slash policy." if resolution_event else "Reviewer consensus upheld the dispute."
        dispute.resolved_at = datetime.now(timezone.utc)
        if resolution_event:
            dispute.resolution_event = resolution_event
        return account, resolution_event

    if dismiss_count >= threshold:
        resolution_event = None
        account = None
        if float(dispute.auto_holdback_amount or 0.0) > 0 and float(dispute.subject.bond_account.holdback_balance if dispute.subject.bond_account else 0.0) > 0:
            amount = min(float(dispute.auto_holdback_amount or 0.0), float(dispute.subject.bond_account.holdback_balance or 0.0))
            account, resolution_event = record_bond_event(
                dispute.subject,
                event_type="holdback_released",
                amount=amount,
                reason=f"Reviewer consensus dismissed dispute {dispute.id}: {dispute.title}",
                evidence_url=dispute.evidence_url,
                event_payload={"dispute_id": dispute.id, "category": dispute.category, "phase": "resolution"},
            )
        dispute.status = "resolved"
        dispute.resolution = "dismissed"
        dispute.resolution_summary = "Reviewer consensus dismissed the dispute and released any temporary holdback."
        dispute.resolved_at = datetime.now(timezone.utc)
        if resolution_event:
            dispute.resolution_event = resolution_event
        return account, resolution_event

    return None
