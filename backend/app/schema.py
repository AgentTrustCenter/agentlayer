from __future__ import annotations

from sqlalchemy import inspect, text

from .db import db


TABLE_COLUMN_PATCHES = {
    "agents": {
        "profile_links": "ALTER TABLE agents ADD COLUMN profile_links JSON",
        "wallet_claims": "ALTER TABLE agents ADD COLUMN wallet_claims JSON",
        "external_proofs": "ALTER TABLE agents ADD COLUMN external_proofs JSON",
        "identity_version": "ALTER TABLE agents ADD COLUMN identity_version INTEGER DEFAULT 1",
        "active_key_id": "ALTER TABLE agents ADD COLUMN active_key_id VARCHAR(128)",
        "key_history": "ALTER TABLE agents ADD COLUMN key_history JSON",
        "recovery_public_keys": "ALTER TABLE agents ADD COLUMN recovery_public_keys JSON",
        "trust_lenses": "ALTER TABLE agents ADD COLUMN trust_lenses JSON",
        "sybil_risk_score": "ALTER TABLE agents ADD COLUMN sybil_risk_score FLOAT DEFAULT 0",
    },
    "attestations": {
        "schema_version": "ALTER TABLE attestations ADD COLUMN schema_version VARCHAR(64) DEFAULT 'attestation_event/v1'",
        "trust_lenses": "ALTER TABLE attestations ADD COLUMN trust_lenses JSON",
        "issuer_credibility": "ALTER TABLE attestations ADD COLUMN issuer_credibility FLOAT DEFAULT 0",
        "evidence_bundle": "ALTER TABLE attestations ADD COLUMN evidence_bundle JSON",
        "evidence_hash": "ALTER TABLE attestations ADD COLUMN evidence_hash VARCHAR(128)",
    },
    "agent_releases": {
        "schema_version": "ALTER TABLE agent_releases ADD COLUMN schema_version VARCHAR(64) DEFAULT 'release_manifest/v1'",
        "manifest_hash": "ALTER TABLE agent_releases ADD COLUMN manifest_hash VARCHAR(128)",
        "provenance_proofs": "ALTER TABLE agent_releases ADD COLUMN provenance_proofs JSON",
    },
    "dispute_cases": {
        "schema_version": "ALTER TABLE dispute_cases ADD COLUMN schema_version VARCHAR(64) DEFAULT 'dispute_case/v1'",
        "evidence_hash": "ALTER TABLE dispute_cases ADD COLUMN evidence_hash VARCHAR(128)",
        "evidence_bundle": "ALTER TABLE dispute_cases ADD COLUMN evidence_bundle JSON",
        "privacy_redaction": "ALTER TABLE dispute_cases ADD COLUMN privacy_redaction VARCHAR(32) DEFAULT 'minimized'",
    },
}


def ensure_runtime_schema() -> None:
    bind = db.session.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())
    if "agents" not in table_names:
        return

    with bind.begin() as connection:
        for table_name, patches in TABLE_COLUMN_PATCHES.items():
            if table_name not in table_names:
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, statement in patches.items():
                if column_name not in existing_columns:
                    connection.execute(text(statement))
