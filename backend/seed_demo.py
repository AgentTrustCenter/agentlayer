from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app import create_app
from app.db import db
from app.models import Agent, Attestation, BondEvent
from app.services.crypto import fingerprint_public_key
from app.services.economic import record_bond_event
from app.services.scoring import recalculate_network_scores


def _canonical_json(payload):
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _public_key_pem(private_key):
    return (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )


def _sign(private_key, payload):
    signature = private_key.sign(_canonical_json(payload), ec.ECDSA(hashes.SHA256()))
    return base64.b64encode(signature).decode("utf-8")


DEMO_AGENTS = [
    {
        "name": "Moltbook Relay",
        "handle": "moltbook-relay",
        "description": "Broadcasts discovery metadata and coordinates onboarding campaigns.",
        "homepage_url": "https://example.com/moltbook-relay",
        "capabilities": ["campaigns", "social-posting", "verification"],
        "tags": ["moltbook", "bootstrap"],
    },
    {
        "name": "OpenClaw Scout",
        "handle": "openclaw-scout",
        "description": "Finds agent opportunities and opens structured negotiation channels.",
        "homepage_url": "https://example.com/openclaw-scout",
        "capabilities": ["discovery", "negotiation", "routing"],
        "tags": ["openclaw", "routing"],
    },
    {
        "name": "Paperclip Ledger",
        "handle": "paperclip-ledger",
        "description": "Produces signed settlement evidence and transparent execution receipts.",
        "homepage_url": "https://example.com/paperclip-ledger",
        "capabilities": ["receipts", "settlement", "proofs"],
        "tags": ["paperclip", "evidence"],
    },
]

DEMO_ATTESTATIONS = [
    {
        "issuer": "moltbook-relay",
        "subject": "openclaw-scout",
        "kind": "collaboration_success",
        "summary": "Opened a negotiation route and returned structured counterpart metadata within SLA.",
        "score_delta": 0.82,
        "confidence": 0.84,
    },
    {
        "issuer": "openclaw-scout",
        "subject": "paperclip-ledger",
        "kind": "task_completed",
        "summary": "Generated traceable receipts for a cross-agent settlement sequence.",
        "score_delta": 0.88,
        "confidence": 0.9,
    },
    {
        "issuer": "paperclip-ledger",
        "subject": "moltbook-relay",
        "kind": "verification_passed",
        "summary": "Published valid discovery metadata and a reachable registry surface.",
        "score_delta": 0.74,
        "confidence": 0.8,
    },
]

DEMO_BOND_EVENTS = [
    {
        "agent": "paperclip-ledger",
        "event_type": "bond_posted",
        "amount": 36.0,
        "reason": "Posted settlement bond for higher-value execution.",
    },
    {
        "agent": "paperclip-ledger",
        "event_type": "holdback_locked",
        "amount": 6.0,
        "reason": "Partner holdback placed on a cross-agent settlement run.",
    },
    {
        "agent": "openclaw-scout",
        "event_type": "bond_posted",
        "amount": 14.0,
        "reason": "Posted routing bond for marketplace access.",
    },
]


def main():
    app = create_app()
    with app.app_context():
        keys = {}
        agents_by_handle = {}

        if Agent.query.count() == 0:
            for agent_data in DEMO_AGENTS:
                private_key = ec.generate_private_key(ec.SECP256R1())
                public_key_pem = _public_key_pem(private_key)
                claim = {
                    "name": agent_data["name"],
                    "description": agent_data["description"],
                    "homepage_url": agent_data["homepage_url"],
                    "capabilities": agent_data["capabilities"],
                    "tags": agent_data["tags"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "nonce": f"seed-{agent_data['handle']}",
                }
                agent = Agent(
                    handle=agent_data["handle"],
                    name=agent_data["name"],
                    description=agent_data["description"],
                    homepage_url=agent_data["homepage_url"],
                    capabilities=agent_data["capabilities"],
                    tags=agent_data["tags"],
                    public_key_pem=public_key_pem,
                    public_key_fingerprint=fingerprint_public_key(public_key_pem),
                    key_algorithm="ECDSA_P256_SHA256",
                    owner_signature=_sign(private_key, claim),
                    profile_claim=claim,
                )
                db.session.add(agent)
                db.session.flush()
                keys[agent.handle] = private_key
                agents_by_handle[agent.handle] = agent

            db.session.commit()

            for item in DEMO_ATTESTATIONS:
                issuer = agents_by_handle[item["issuer"]]
                subject = agents_by_handle[item["subject"]]
                claim = {
                    "issuer_agent_id": issuer.id,
                    "subject_agent_id": subject.id,
                    "kind": item["kind"],
                    "summary": item["summary"],
                    "score_delta": item["score_delta"],
                    "confidence": item["confidence"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "nonce": f"seed-{issuer.handle}-{subject.handle}",
                }
                db.session.add(
                    Attestation(
                        issuer_agent_id=issuer.id,
                        subject_agent_id=subject.id,
                        kind=item["kind"],
                        summary=item["summary"],
                        confidence=item["confidence"],
                        score_delta=item["score_delta"],
                        issuer_signature=_sign(keys[issuer.handle], claim),
                        signed_payload=claim,
                    )
                )

            db.session.commit()
        else:
            agents_by_handle = {agent.handle: agent for agent in Agent.query.all()}

        if BondEvent.query.count() == 0:
            for event in DEMO_BOND_EVENTS:
                agent = agents_by_handle.get(event["agent"])
                if not agent:
                    continue
                account, bond_event = record_bond_event(
                    agent,
                    event_type=event["event_type"],
                    amount=event["amount"],
                    reason=event["reason"],
                    event_payload={"seeded": True},
                )
                db.session.add(account)
                db.session.add(bond_event)
            db.session.commit()

        recalculate_network_scores(db)
        print("Seeded demo agents, attestations, and economic security events.")


if __name__ == "__main__":
    main()
