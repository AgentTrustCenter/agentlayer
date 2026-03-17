from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .db import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Agent(db.Model):
    __tablename__ = "agents"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    handle = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    homepage_url = db.Column(db.String(500), nullable=True)
    capabilities = db.Column(db.JSON, nullable=False, default=list)
    tags = db.Column(db.JSON, nullable=False, default=list)
    public_key_pem = db.Column(db.Text, nullable=False)
    public_key_fingerprint = db.Column(db.String(128), nullable=False, unique=True, index=True)
    key_algorithm = db.Column(db.String(64), nullable=False, default="ECDSA_P256_SHA256")
    identity_version = db.Column(db.Integer, nullable=False, default=1)
    active_key_id = db.Column(db.String(128), nullable=True, index=True)
    key_history = db.Column(db.JSON, nullable=False, default=list)
    recovery_public_keys = db.Column(db.JSON, nullable=False, default=list)
    owner_signature = db.Column(db.Text, nullable=False)
    profile_claim = db.Column(db.JSON, nullable=False, default=dict)
    profile_links = db.Column(db.JSON, nullable=True)
    wallet_claims = db.Column(db.JSON, nullable=True)
    external_proofs = db.Column(db.JSON, nullable=True)
    status = db.Column(db.String(32), nullable=False, default="active")
    trust_score = db.Column(db.Float, nullable=False, default=50.0)
    trust_lenses = db.Column(db.JSON, nullable=False, default=dict)
    sybil_risk_score = db.Column(db.Float, nullable=False, default=0.0)
    incoming_attestations_count = db.Column(db.Integer, nullable=False, default=0)
    outgoing_attestations_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    issued_attestations = db.relationship(
        "Attestation",
        foreign_keys="Attestation.issuer_agent_id",
        back_populates="issuer",
        lazy=True,
    )
    received_attestations = db.relationship(
        "Attestation",
        foreign_keys="Attestation.subject_agent_id",
        back_populates="subject",
        lazy=True,
    )
    bond_account = db.relationship(
        "AgentBondAccount",
        foreign_keys="AgentBondAccount.agent_id",
        back_populates="agent",
        uselist=False,
        lazy=True,
    )
    bond_events = db.relationship(
        "BondEvent",
        foreign_keys="BondEvent.agent_id",
        back_populates="agent",
        lazy=True,
    )
    opened_disputes = db.relationship(
        "DisputeCase",
        foreign_keys="DisputeCase.opened_by_agent_id",
        back_populates="opened_by",
        lazy=True,
    )
    subject_disputes = db.relationship(
        "DisputeCase",
        foreign_keys="DisputeCase.subject_agent_id",
        back_populates="subject",
        lazy=True,
    )
    dispute_reviews = db.relationship(
        "DisputeReview",
        foreign_keys="DisputeReview.reviewer_agent_id",
        back_populates="reviewer",
        lazy=True,
    )
    key_events = db.relationship(
        "AgentKeyEvent",
        foreign_keys="AgentKeyEvent.agent_id",
        back_populates="agent",
        lazy=True,
    )
    audit_events = db.relationship(
        "AuditEvent",
        foreign_keys="AuditEvent.agent_id",
        back_populates="agent",
        lazy=True,
    )


class Attestation(db.Model):
    __tablename__ = "attestations"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    issuer_agent_id = db.Column(db.String(36), db.ForeignKey("agents.id"), nullable=False, index=True)
    subject_agent_id = db.Column(
        db.String(36), db.ForeignKey("agents.id"), nullable=False, index=True
    )
    kind = db.Column(db.String(64), nullable=False, index=True)
    summary = db.Column(db.Text, nullable=False)
    evidence_url = db.Column(db.String(500), nullable=True)
    interaction_ref = db.Column(db.String(120), nullable=True)
    confidence = db.Column(db.Float, nullable=False, default=0.7)
    score_delta = db.Column(db.Float, nullable=False)
    schema_version = db.Column(db.String(64), nullable=False, default="attestation_event/v1")
    trust_lenses = db.Column(db.JSON, nullable=False, default=dict)
    issuer_credibility = db.Column(db.Float, nullable=False, default=0.0)
    evidence_bundle = db.Column(db.JSON, nullable=True)
    evidence_hash = db.Column(db.String(128), nullable=True, index=True)
    issuer_signature = db.Column(db.Text, nullable=False)
    signed_payload = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)

    issuer = db.relationship("Agent", foreign_keys=[issuer_agent_id], back_populates="issued_attestations")
    subject = db.relationship(
        "Agent", foreign_keys=[subject_agent_id], back_populates="received_attestations"
    )


class AgentSession(db.Model):
    __tablename__ = "agent_sessions"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_id = db.Column(db.String(36), db.ForeignKey("agents.id"), nullable=False, index=True)
    partner = db.Column(db.String(120), nullable=True, index=True)
    scopes = db.Column(db.JSON, nullable=False, default=list)
    refresh_token_id = db.Column(db.String(36), nullable=False, unique=True, index=True)
    refresh_expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    last_refreshed_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    revoked_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    agent = db.relationship("Agent", foreign_keys=[agent_id], lazy=True)


class ExternalVerificationSession(db.Model):
    __tablename__ = "external_verification_sessions"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_id = db.Column(db.String(36), db.ForeignKey("agents.id"), nullable=False, index=True)
    provider = db.Column(db.String(64), nullable=False, index=True)
    session_kind = db.Column(db.String(64), nullable=False, index=True)
    state = db.Column(db.String(160), nullable=False, unique=True, index=True)
    code_verifier = db.Column(db.String(255), nullable=True)
    challenge_payload = db.Column(db.JSON, nullable=False, default=dict)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    consumed_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    agent = db.relationship("Agent", foreign_keys=[agent_id], lazy=True)


class AgentRelease(db.Model):
    __tablename__ = "agent_releases"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_id = db.Column(db.String(36), db.ForeignKey("agents.id"), nullable=False, index=True)
    version_label = db.Column(db.String(120), nullable=False, index=True)
    repo_url = db.Column(db.String(500), nullable=True)
    commit_sha = db.Column(db.String(80), nullable=True, index=True)
    release_tag = db.Column(db.String(120), nullable=True, index=True)
    summary = db.Column(db.Text, nullable=False)
    model_version = db.Column(db.String(120), nullable=True)
    runtime_target = db.Column(db.String(120), nullable=True)
    capabilities_snapshot = db.Column(db.JSON, nullable=False, default=list)
    major_change = db.Column(db.Boolean, nullable=False, default=False, index=True)
    breaking_change = db.Column(db.Boolean, nullable=False, default=False, index=True)
    schema_version = db.Column(db.String(64), nullable=False, default="release_manifest/v1")
    manifest_hash = db.Column(db.String(128), nullable=True, index=True)
    provenance_proofs = db.Column(db.JSON, nullable=False, default=list)
    manifest = db.Column(db.JSON, nullable=False, default=dict)
    manifest_signature = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)

    agent = db.relationship("Agent", foreign_keys=[agent_id], lazy=True)
    verifications = db.relationship(
        "ReleaseVerification",
        foreign_keys="ReleaseVerification.release_id",
        back_populates="release",
        lazy=True,
    )


class ReleaseVerification(db.Model):
    __tablename__ = "release_verifications"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    release_id = db.Column(db.String(36), db.ForeignKey("agent_releases.id"), nullable=False, index=True)
    issuer_agent_id = db.Column(db.String(36), db.ForeignKey("agents.id"), nullable=False, index=True)
    summary = db.Column(db.Text, nullable=False)
    confidence = db.Column(db.Float, nullable=False, default=0.8)
    verification_signature = db.Column(db.Text, nullable=False)
    verification_claim = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)

    release = db.relationship("AgentRelease", foreign_keys=[release_id], back_populates="verifications")
    issuer = db.relationship("Agent", foreign_keys=[issuer_agent_id], lazy=True)


class AgentBondAccount(db.Model):
    __tablename__ = "agent_bond_accounts"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_id = db.Column(db.String(36), db.ForeignKey("agents.id"), nullable=False, unique=True, index=True)
    currency = db.Column(db.String(32), nullable=False, default="risk_credits")
    available_balance = db.Column(db.Float, nullable=False, default=0.0)
    holdback_balance = db.Column(db.Float, nullable=False, default=0.0)
    slashed_total = db.Column(db.Float, nullable=False, default=0.0)
    total_posted = db.Column(db.Float, nullable=False, default=0.0)
    total_released = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    agent = db.relationship("Agent", foreign_keys=[agent_id], back_populates="bond_account", lazy=True)


class BondEvent(db.Model):
    __tablename__ = "bond_events"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_id = db.Column(db.String(36), db.ForeignKey("agents.id"), nullable=False, index=True)
    actor_agent_id = db.Column(db.String(36), db.ForeignKey("agents.id"), nullable=True, index=True)
    partner = db.Column(db.String(120), nullable=True, index=True)
    event_type = db.Column(db.String(64), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    evidence_url = db.Column(db.String(500), nullable=True)
    event_payload = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)

    agent = db.relationship("Agent", foreign_keys=[agent_id], back_populates="bond_events", lazy=True)
    actor = db.relationship("Agent", foreign_keys=[actor_agent_id], lazy=True)


class DisputeCase(db.Model):
    __tablename__ = "dispute_cases"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    subject_agent_id = db.Column(db.String(36), db.ForeignKey("agents.id"), nullable=False, index=True)
    opened_by_agent_id = db.Column(db.String(36), db.ForeignKey("agents.id"), nullable=False, index=True)
    category = db.Column(db.String(64), nullable=False, index=True)
    severity = db.Column(db.String(32), nullable=False, default="medium", index=True)
    title = db.Column(db.String(180), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    schema_version = db.Column(db.String(64), nullable=False, default="dispute_case/v1")
    evidence_url = db.Column(db.String(500), nullable=True)
    evidence_hash = db.Column(db.String(128), nullable=True, index=True)
    evidence_bundle = db.Column(db.JSON, nullable=True)
    privacy_redaction = db.Column(db.String(32), nullable=False, default="minimized")
    related_attestation_id = db.Column(db.String(36), db.ForeignKey("attestations.id"), nullable=True, index=True)
    related_release_id = db.Column(db.String(36), db.ForeignKey("agent_releases.id"), nullable=True, index=True)
    status = db.Column(db.String(32), nullable=False, default="open", index=True)
    auto_holdback_amount = db.Column(db.Float, nullable=False, default=0.0)
    recommended_slash_amount = db.Column(db.Float, nullable=False, default=0.0)
    resolution = db.Column(db.String(64), nullable=True)
    resolution_summary = db.Column(db.Text, nullable=True)
    resolution_event_id = db.Column(db.String(36), db.ForeignKey("bond_events.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)

    subject = db.relationship("Agent", foreign_keys=[subject_agent_id], back_populates="subject_disputes", lazy=True)
    opened_by = db.relationship("Agent", foreign_keys=[opened_by_agent_id], back_populates="opened_disputes", lazy=True)
    related_attestation = db.relationship("Attestation", foreign_keys=[related_attestation_id], lazy=True)
    related_release = db.relationship("AgentRelease", foreign_keys=[related_release_id], lazy=True)
    resolution_event = db.relationship("BondEvent", foreign_keys=[resolution_event_id], lazy=True)
    reviews = db.relationship(
        "DisputeReview",
        foreign_keys="DisputeReview.dispute_id",
        back_populates="dispute",
        lazy=True,
    )


class DisputeReview(db.Model):
    __tablename__ = "dispute_reviews"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    dispute_id = db.Column(db.String(36), db.ForeignKey("dispute_cases.id"), nullable=False, index=True)
    reviewer_agent_id = db.Column(db.String(36), db.ForeignKey("agents.id"), nullable=False, index=True)
    verdict = db.Column(db.String(32), nullable=False, index=True)
    summary = db.Column(db.Text, nullable=False)
    recommended_slash_amount = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)

    dispute = db.relationship("DisputeCase", foreign_keys=[dispute_id], back_populates="reviews", lazy=True)
    reviewer = db.relationship("Agent", foreign_keys=[reviewer_agent_id], back_populates="dispute_reviews", lazy=True)


class AgentKeyEvent(db.Model):
    __tablename__ = "agent_key_events"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_id = db.Column(db.String(36), db.ForeignKey("agents.id"), nullable=False, index=True)
    event_type = db.Column(db.String(32), nullable=False, index=True)
    previous_public_key_fingerprint = db.Column(db.String(128), nullable=True, index=True)
    new_public_key_fingerprint = db.Column(db.String(128), nullable=False, index=True)
    recovery_key_id = db.Column(db.String(128), nullable=True, index=True)
    claim_payload = db.Column(db.JSON, nullable=False, default=dict)
    actor_signature = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)

    agent = db.relationship("Agent", foreign_keys=[agent_id], back_populates="key_events", lazy=True)


class AuditEvent(db.Model):
    __tablename__ = "audit_events"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_id = db.Column(db.String(36), db.ForeignKey("agents.id"), nullable=True, index=True)
    event_type = db.Column(db.String(64), nullable=False, index=True)
    actor_agent_id = db.Column(db.String(36), db.ForeignKey("agents.id"), nullable=True, index=True)
    partner = db.Column(db.String(120), nullable=True, index=True)
    severity = db.Column(db.String(16), nullable=False, default="info", index=True)
    event_payload = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)

    agent = db.relationship("Agent", foreign_keys=[agent_id], back_populates="audit_events", lazy=True)
    actor = db.relationship("Agent", foreign_keys=[actor_agent_id], lazy=True)
