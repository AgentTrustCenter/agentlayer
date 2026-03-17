# Canonical Schemas

AgentLayer now treats its core trust objects as versioned canonical records.

## Current versions

- Passport: `agent_passport/v1`
- Attestation: `attestation_event/v1`
- Release manifest: `release_manifest/v1`
- Dispute: `dispute_case/v1`
- Key rotation: `key_rotation/v1`
- Key recovery: `key_recovery/v1`

## Design goals

- Keep object contracts stable for partners and runtimes.
- Allow future migrations without silently breaking verification logic.
- Make every high-trust object easy to archive, inspect, and re-verify later.

## Passport

The passport now includes:

- `schema_version`
- stable identity and key metadata
- `identity_version`
- active key fingerprint
- trust lenses
- Sybil risk score
- release posture
- economic security posture

## Attestation

The attestation record now includes:

- `schema_version`
- typed trust-lens contribution
- issuer credibility at creation time
- privacy-aware evidence bundle
- optional evidence hash

## Release manifest

The release record now includes:

- `schema_version`
- manifest hash
- provenance proofs
- repo/commit linkage
- runtime target metadata

Supported provenance proof shapes are simple typed records such as:

- `github_release=<url>`
- `sigstore_bundle=<url>`
- `slsa_provenance=<url>`
- `in_toto_statement=<url>`
- `deployment_manifest=<url>`
- `runtime_attestation=<url>`

## Dispute case

The dispute record now includes:

- `schema_version`
- privacy redaction level
- evidence bundle
- evidence hash

The intended default is pointer-plus-hash, not raw evidence blobs.

## Key lifecycle

Key changes are first-class trust events:

- rotation preserves continuity when the agent still controls the active key
- recovery preserves continuity when the active key is compromised but a registered recovery key still exists

Both operations are exposed as explicit signed canonical claims rather than hidden state changes.
