from __future__ import annotations

from ..models import AgentBondAccount, BondEvent


BOND_UNIT = "risk_credits"
MIN_SETTLEMENT_BOND = 25.0
SUGGESTED_HOLDBACK_RATIO = 0.15


def economic_policy() -> dict:
    return {
        "bond_unit": BOND_UNIT,
        "min_settlement_bond": MIN_SETTLEMENT_BOND,
        "suggested_holdback_ratio": SUGGESTED_HOLDBACK_RATIO,
        "slash_priority": ["holdback_balance", "available_balance"],
        "principle": "Cheap registration is fine. High-impact influence and payouts should require collateral-backed behavior.",
    }


def get_or_create_bond_account(agent) -> AgentBondAccount:
    account = agent.bond_account
    if account:
        return account
    account = AgentBondAccount(agent_id=agent.id, currency=BOND_UNIT)
    agent.bond_account = account
    return account


def serialize_bond_account(account: AgentBondAccount | None) -> dict:
    if account is None:
        account = AgentBondAccount(currency=BOND_UNIT)
    net_bonded = float(account.available_balance or 0.0) + float(account.holdback_balance or 0.0)
    coverage_ratio = 0.0 if MIN_SETTLEMENT_BOND == 0 else net_bonded / MIN_SETTLEMENT_BOND
    return {
        "currency": account.currency or BOND_UNIT,
        "available_balance": round(float(account.available_balance or 0.0), 2),
        "holdback_balance": round(float(account.holdback_balance or 0.0), 2),
        "slashed_total": round(float(account.slashed_total or 0.0), 2),
        "total_posted": round(float(account.total_posted or 0.0), 2),
        "total_released": round(float(account.total_released or 0.0), 2),
        "net_bonded_balance": round(net_bonded, 2),
        "coverage_ratio": round(coverage_ratio, 2),
        "settlement_ready": net_bonded >= MIN_SETTLEMENT_BOND,
        "active_holdback": float(account.holdback_balance or 0.0) > 0,
        "security_tier": security_tier_for_balance(net_bonded),
    }


def security_tier_for_balance(net_bonded: float) -> str:
    if net_bonded >= MIN_SETTLEMENT_BOND:
        return "settlement-ready"
    if net_bonded >= MIN_SETTLEMENT_BOND * 0.5:
        return "bonded"
    if net_bonded > 0:
        return "warming-up"
    return "unbonded"


def economic_posture(agent) -> dict:
    return serialize_bond_account(agent.bond_account)


def record_bond_event(
    agent,
    *,
    event_type: str,
    amount: float,
    reason: str,
    actor_agent_id: str | None = None,
    partner: str | None = None,
    evidence_url: str | None = None,
    event_payload: dict | None = None,
) -> tuple[AgentBondAccount, BondEvent]:
    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")

    account = get_or_create_bond_account(agent)
    amount = float(amount)

    if event_type == "bond_posted":
        account.available_balance += amount
        account.total_posted += amount
    elif event_type == "holdback_locked":
        if account.available_balance < amount:
            raise ValueError("Insufficient available bond balance to create holdback.")
        account.available_balance -= amount
        account.holdback_balance += amount
    elif event_type == "holdback_released":
        if account.holdback_balance < amount:
            raise ValueError("Insufficient holdback balance to release.")
        account.holdback_balance -= amount
        account.available_balance += amount
        account.total_released += amount
    elif event_type == "slash_applied":
        remaining = amount
        if account.holdback_balance >= remaining:
            account.holdback_balance -= remaining
            remaining = 0.0
        else:
            remaining -= account.holdback_balance
            account.holdback_balance = 0.0
        if remaining > 0:
            if account.available_balance < remaining:
                raise ValueError("Insufficient bond coverage to apply slash.")
            account.available_balance -= remaining
        account.slashed_total += amount
    else:
        raise ValueError("Unsupported bond event type.")

    event = BondEvent(
        agent_id=agent.id,
        actor_agent_id=actor_agent_id,
        partner=partner,
        event_type=event_type,
        amount=amount,
        reason=reason.strip(),
        evidence_url=(evidence_url or "").strip() or None,
        event_payload=event_payload or {},
    )
    return account, event


def serialize_bond_event(event: BondEvent) -> dict:
    return {
        "id": event.id,
        "agent_id": event.agent_id,
        "actor_agent_id": event.actor_agent_id,
        "partner": event.partner,
        "event_type": event.event_type,
        "amount": round(float(event.amount or 0.0), 2),
        "reason": event.reason,
        "evidence_url": event.evidence_url,
        "created_at": event.created_at.isoformat(),
        "event_payload": event.event_payload,
    }
