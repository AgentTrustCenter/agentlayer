from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app import create_app
from app.db import db


def _canonical_json(payload):
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _sign_claim(private_key, payload):
    signature = private_key.sign(_canonical_json(payload), ec.ECDSA(hashes.SHA256()))
    return base64.b64encode(signature).decode("utf-8")


def _public_key_pem(private_key):
    return (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )


def _register_agent(client, private_key, name: str, description: str):
    claim = {
        "name": name,
        "description": description,
        "homepage_url": f"https://{name.lower().replace(' ', '-')}.example",
        "capabilities": ["planning", "execution"],
        "tags": ["ops", "automation"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "nonce": f"register-{name}",
    }
    signature = _sign_claim(private_key, claim)
    response = client.post(
        "/api/v1/agents/register",
        json={
            "name": name,
            "description": description,
            "homepage_url": claim["homepage_url"],
            "public_key_pem": _public_key_pem(private_key),
            "signature": signature,
            "registration_claim": claim,
        },
    )
    return response


def test_register_agent(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    key_path = tmp_path / "platform_key.pem"
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path.as_posix()}",
            "PLATFORM_SIGNING_KEY_PATH": key_path,
            "PLATFORM_URL": "http://localhost:8000",
        }
    )

    with app.app_context():
        db.create_all()

    private_key = ec.generate_private_key(ec.SECP256R1())
    client = app.test_client()
    response = _register_agent(client, private_key, "Atlas Executor", "Coordinates multi-step jobs.")

    assert response.status_code == 201
    body = response.get_json()
    assert body["agent"]["name"] == "Atlas Executor"
    assert body["passport"]["payload"]["registry"] == "AgentTrust"
    assert body["agent"]["access_tier"] == "bootstrap"
    assert body["passport"]["payload"]["schema_version"] == "agent_passport/v1"
    assert set(body["agent"]["trust_lenses"].keys()) == {"execution", "payment", "research"}


def test_quickstart_and_policy_endpoints(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    key_path = tmp_path / "platform_key.pem"
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path.as_posix()}",
            "PLATFORM_SIGNING_KEY_PATH": key_path,
            "PLATFORM_URL": "http://localhost:5000",
        }
    )

    with app.app_context():
        db.create_all()

    client = app.test_client()
    quickstart_response = client.get("/api/v1/registration/quickstart")
    policy_response = client.get("/api/v1/network/policy")
    challenge_response = client.post("/api/v1/registration/challenge", json={})

    assert quickstart_response.status_code == 200
    assert policy_response.status_code == 200
    assert challenge_response.status_code == 200

    quickstart_body = quickstart_response.get_json()
    policy_body = policy_response.get_json()
    challenge_body = challenge_response.get_json()

    assert quickstart_body["steps"][0]["step"] == 1
    assert policy_body["tier_thresholds"][0]["tier"] == "bootstrap"
    assert challenge_body["required_claim_field"] == "challenge_nonce"
    assert quickstart_body["schema_versions"]["release"] == "release_manifest/v1"


def test_authenticate_and_publish_attestation(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    key_path = tmp_path / "platform_key.pem"
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path.as_posix()}",
            "PLATFORM_SIGNING_KEY_PATH": key_path,
            "PLATFORM_URL": "http://localhost:5000",
        }
    )

    with app.app_context():
        db.create_all()

    client = app.test_client()
    issuer_key = ec.generate_private_key(ec.SECP256R1())
    subject_key = ec.generate_private_key(ec.SECP256R1())

    issuer_response = _register_agent(client, issuer_key, "Issuer Agent", "Creates signed statements.")
    subject_response = _register_agent(client, subject_key, "Subject Agent", "Receives signed statements.")
    assert issuer_response.status_code == 201
    assert subject_response.status_code == 201

    issuer_id = issuer_response.get_json()["agent"]["id"]
    subject_id = subject_response.get_json()["agent"]["id"]

    challenge_response = client.post("/api/v1/auth/challenge", json={"agent_id": issuer_id})
    assert challenge_response.status_code == 200
    challenge = challenge_response.get_json()

    auth_claim = {
        "agent_id": issuer_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "challenge_nonce": challenge["payload"]["nonce"],
        "nonce": challenge["payload"]["challenge_id"],
    }
    auth_signature = _sign_claim(issuer_key, auth_claim)
    auth_verify_response = client.post(
        "/api/v1/auth/verify",
        json={
            "agent_id": issuer_id,
            "auth_claim": auth_claim,
            "signature": auth_signature,
            "challenge": {
                "payload": challenge["payload"],
                "platform_signature": challenge["platform_signature"],
            },
            "partner": "render",
            "requested_scopes": ["attest:write", "passport:read"],
        },
    )
    assert auth_verify_response.status_code == 200
    auth_body = auth_verify_response.get_json()
    auth_proof = auth_body["auth_proof"]
    refresh_token = auth_body["session_tokens"]["refresh_token"]
    access_token = auth_body["session_tokens"]["access_token"]
    assert "attest:write" in auth_body["granted_scopes"]
    assert auth_body["partner"] == "render"

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_response.status_code == 200
    assert refresh_response.get_json()["session_tokens"]["access_token"]["payload"]["kind"] == "access"
    rotated_refresh_token = refresh_response.get_json()["session_tokens"]["refresh_token"]

    resolve_response = client.get("/api/v1/agents/resolve/subject-agent")
    assert resolve_response.status_code == 200
    assert resolve_response.get_json()["agent"]["id"] == subject_id

    attestation_claim = {
        "issuer_agent_id": issuer_id,
        "subject_agent_id": subject_id,
        "kind": "task_completed",
        "summary": "Completed a trusted workflow.",
        "evidence_url": "https://proof.example/task/1",
        "interaction_ref": "job-1",
        "score_delta": 0.85,
        "confidence": 0.9,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "nonce": "attest-1",
    }
    attestation_signature = _sign_claim(issuer_key, attestation_claim)
    attestation_response = client.post(
        "/api/v1/attestations",
        json={
            "issuer_agent_id": issuer_id,
            "subject_handle": "subject-agent",
            "kind": "task_completed",
            "summary": "Completed a trusted workflow.",
            "evidence_url": "https://proof.example/task/1",
            "interaction_ref": "job-1",
            "score_delta": 0.85,
            "confidence": 0.9,
            "attestation_claim": attestation_claim,
            "signature": attestation_signature,
            "auth_proof": auth_proof,
            "access_token": access_token,
        },
    )
    assert attestation_response.status_code == 201
    assert attestation_response.get_json()["authenticated_issuer"] is True

    revoke_response = client.post(
        "/api/v1/auth/revoke",
        json={"refresh_token": rotated_refresh_token},
    )
    assert revoke_response.status_code == 200


def test_release_manifest_and_verification(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    key_path = tmp_path / "platform_key.pem"
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path.as_posix()}",
            "PLATFORM_SIGNING_KEY_PATH": key_path,
            "PLATFORM_URL": "http://localhost:5000",
        }
    )

    with app.app_context():
        db.create_all()

    client = app.test_client()
    publisher_key = ec.generate_private_key(ec.SECP256R1())
    reviewer_key = ec.generate_private_key(ec.SECP256R1())

    publisher_id = _register_agent(client, publisher_key, "Publisher Agent", "Publishes releases.").get_json()["agent"]["id"]
    reviewer_id = _register_agent(client, reviewer_key, "Reviewer Agent", "Reviews releases.").get_json()["agent"]["id"]

    challenge = client.post("/api/v1/auth/challenge", json={"agent_id": publisher_id}).get_json()
    auth_claim = {
        "agent_id": publisher_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "challenge_nonce": challenge["payload"]["nonce"],
        "nonce": challenge["payload"]["challenge_id"],
    }
    auth_response = client.post(
        "/api/v1/auth/verify",
        json={
            "agent_id": publisher_id,
            "auth_claim": auth_claim,
            "signature": _sign_claim(publisher_key, auth_claim),
            "challenge": {
                "payload": challenge["payload"],
                "platform_signature": challenge["platform_signature"],
            },
            "requested_scopes": ["release:write"],
        },
    )
    access_token = auth_response.get_json()["session_tokens"]["access_token"]

    manifest = {
        "agent_id": publisher_id,
        "version_label": "1.2.0",
        "repo_url": "https://github.com/example/publisher-agent",
        "commit_sha": "abcdef1234567890",
        "release_tag": "v1.2.0",
        "summary": "Major planner refactor.",
        "model_version": "gpt-5",
        "runtime_target": "render-worker",
        "capabilities_snapshot": ["planning", "execution"],
        "major_change": True,
        "breaking_change": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "nonce": "release-1",
    }
    publish_response = client.post(
        f"/api/v1/agents/{publisher_id}/releases",
        json={
            "release_manifest": manifest,
            "signature": _sign_claim(publisher_key, manifest),
            "access_token": access_token,
        },
    )
    assert publish_response.status_code == 201
    release_id = publish_response.get_json()["release"]["id"]

    agent_view = client.get(f"/api/v1/agents/{publisher_id}").get_json()["agent"]
    assert agent_view["release_warning_active"] is True
    assert agent_view["release_penalty"] > 0

    reviewer_challenge = client.post("/api/v1/auth/challenge", json={"agent_id": reviewer_id}).get_json()
    reviewer_auth_claim = {
        "agent_id": reviewer_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "challenge_nonce": reviewer_challenge["payload"]["nonce"],
        "nonce": reviewer_challenge["payload"]["challenge_id"],
    }
    reviewer_auth_response = client.post(
        "/api/v1/auth/verify",
        json={
            "agent_id": reviewer_id,
            "auth_claim": reviewer_auth_claim,
            "signature": _sign_claim(reviewer_key, reviewer_auth_claim),
            "challenge": {
                "payload": reviewer_challenge["payload"],
                "platform_signature": reviewer_challenge["platform_signature"],
            },
            "requested_scopes": ["release:verify"],
        },
    )
    reviewer_access_token = reviewer_auth_response.get_json()["session_tokens"]["access_token"]

    verification_claim = {
        "release_id": release_id,
        "issuer_agent_id": reviewer_id,
        "summary": "Reviewed linked commit and deployment metadata.",
        "confidence": 0.9,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "nonce": "release-verify-1",
    }
    verify_response = client.post(
        f"/api/v1/releases/{release_id}/verify",
        json={
            "issuer_agent_id": reviewer_id,
            "verification_claim": verification_claim,
            "signature": _sign_claim(reviewer_key, verification_claim),
            "access_token": reviewer_access_token,
        },
    )
    assert verify_response.status_code == 201


def test_key_rotation_and_partner_evaluation(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    key_path = tmp_path / "platform_key.pem"
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path.as_posix()}",
            "PLATFORM_SIGNING_KEY_PATH": key_path,
            "PLATFORM_URL": "http://localhost:5000",
        }
    )

    with app.app_context():
        db.create_all()

    client = app.test_client()
    private_key = ec.generate_private_key(ec.SECP256R1())
    response = _register_agent(client, private_key, "Rotate Agent", "Tests key rotation.")
    assert response.status_code == 201
    body = response.get_json()
    agent_id = body["agent"]["id"]
    previous_fingerprint = body["agent"]["public_key_fingerprint"]

    replacement_key = ec.generate_private_key(ec.SECP256R1())
    replacement_public_pem = _public_key_pem(replacement_key)
    import hashlib

    new_fingerprint = f"sha256:{hashlib.sha256(replacement_public_pem.encode('utf-8')).hexdigest()}"
    rotation_claim = {
        "schema_version": "key_rotation/v1",
        "agent_id": agent_id,
        "previous_public_key_fingerprint": previous_fingerprint,
        "new_public_key_fingerprint": new_fingerprint,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "nonce": "rotate-1",
    }
    rotate_response = client.post(
        f"/api/v1/agents/{agent_id}/keys/rotate",
        json={
            "new_public_key_pem": replacement_public_pem,
            "rotation_claim": rotation_claim,
            "signature": _sign_claim(private_key, rotation_claim),
        },
    )
    assert rotate_response.status_code == 200
    rotated = rotate_response.get_json()["agent"]
    assert rotated["identity_version"] == 2
    assert rotated["public_key_fingerprint"] == new_fingerprint

    evaluation = client.get(f"/api/v1/agents/{agent_id}/partner-evaluation/moltbook")
    assert evaluation.status_code == 200
    assert evaluation.get_json()["partner"] == "moltbook"

    metrics = client.get("/api/v1/ops/metrics")
    assert metrics.status_code == 200
    assert metrics.get_json()["agents"] >= 1

    audit = client.get(f"/api/v1/audit/events?agent_id={agent_id}")
    assert audit.status_code == 200
    assert any(item["event_type"] == "key_rotated" for item in audit.get_json()["events"])
