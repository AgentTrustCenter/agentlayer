from __future__ import annotations

from ..models import AuditEvent


def record_audit_event(
    db,
    *,
    event_type: str,
    agent_id: str | None = None,
    actor_agent_id: str | None = None,
    partner: str | None = None,
    severity: str = "info",
    event_payload: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        event_type=event_type,
        agent_id=agent_id,
        actor_agent_id=actor_agent_id,
        partner=partner,
        severity=severity,
        event_payload=event_payload or {},
    )
    db.session.add(event)
    return event


def serialize_audit_event(event: AuditEvent) -> dict:
    return {
        "id": event.id,
        "event_type": event.event_type,
        "agent_id": event.agent_id,
        "actor_agent_id": event.actor_agent_id,
        "partner": event.partner,
        "severity": event.severity,
        "event_payload": event.event_payload,
        "created_at": event.created_at.isoformat(),
    }
