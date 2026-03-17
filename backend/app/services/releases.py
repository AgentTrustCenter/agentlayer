from __future__ import annotations

from datetime import datetime, timezone

from ..models import AgentRelease
from .canonical import RELEASE_SCHEMA_VERSION, normalize_provenance_proofs


def _days_old(created_at: datetime) -> float:
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return max((datetime.now(timezone.utc) - created_at).total_seconds() / 86400, 0.0)


def github_commit_url(repo_url: str | None, commit_sha: str | None) -> str | None:
    if not repo_url or not commit_sha:
        return None
    clean = repo_url.rstrip("/")
    if clean.endswith(".git"):
        clean = clean[:-4]
    return f"{clean}/commit/{commit_sha}"


def serialize_release(release, verification_count: int | None = None) -> dict:
    verifications = verification_count if verification_count is not None else len(release.verifications)
    return {
        "schema_version": release.schema_version or RELEASE_SCHEMA_VERSION,
        "id": release.id,
        "agent_id": release.agent_id,
        "version_label": release.version_label,
        "repo_url": release.repo_url,
        "commit_sha": release.commit_sha,
        "commit_url": github_commit_url(release.repo_url, release.commit_sha),
        "release_tag": release.release_tag,
        "summary": release.summary,
        "model_version": release.model_version,
        "runtime_target": release.runtime_target,
        "capabilities_snapshot": release.capabilities_snapshot,
        "major_change": release.major_change,
        "breaking_change": release.breaking_change,
        "manifest_hash": release.manifest_hash,
        "provenance_proofs": normalize_provenance_proofs(release.provenance_proofs or []),
        "verification_count": verifications,
        "created_at": release.created_at.isoformat(),
    }


def latest_release(agent_id: str):
    return (
        AgentRelease.query.filter_by(agent_id=agent_id)
        .order_by(AgentRelease.created_at.desc())
        .first()
    )


def agent_release_posture(agent) -> dict:
    release = latest_release(agent.id)
    if not release:
        return {
            "latest_release": None,
            "release_penalty": 0.0,
            "release_warning_active": False,
            "release_warning_level": None,
            "release_warning_message": None,
            "release_verification_count": 0,
            "effective_trust_score": round(float(agent.trust_score), 2),
            "base_trust_score": round(float(agent.trust_score), 2),
        }

    verification_count = len(release.verifications)
    age_days = _days_old(release.created_at)
    penalty = 0.0
    warning_level = None
    warning_message = None

    if release.major_change or release.breaking_change:
        if verification_count == 0:
            penalty = 12.0 if release.breaking_change else 8.0
            warning_level = "critical" if release.breaking_change else "warning"
            warning_message = "Latest major release is unconfirmed by peer verifications."
        elif verification_count == 1:
            penalty = 6.0 if release.breaking_change else 3.0
            warning_level = "warning"
            warning_message = "Latest major release has only one verification so far."
    elif verification_count == 0 and age_days <= 7:
        warning_level = "notice"
        warning_message = "Latest release has not yet been verified by peers."

    effective_trust_score = round(max(0.0, float(agent.trust_score) - penalty), 2)
    return {
        "latest_release": serialize_release(release, verification_count),
        "release_penalty": penalty,
        "release_warning_active": warning_level is not None,
        "release_warning_level": warning_level,
        "release_warning_message": warning_message,
        "release_verification_count": verification_count,
        "effective_trust_score": effective_trust_score,
        "base_trust_score": round(float(agent.trust_score), 2),
    }
