# Agent Runtime Flow

## Best-Case Flow

The best-case production flow is:

1. An agent runtime generates a key once, or imports an already trusted key.
2. The private key stays inside the agent runtime.
3. The agent signs its own registration claim.
4. AgentTrust verifies the signature and issues:
   - `agent_id`
   - signed passport
   - eligibility state
   - access tier
5. The agent keeps using the same key for future attestations and auth flows.

## Headless Runtime Operation

With the included runtime client, an agent can now operate end-to-end without the browser:

1. `init` or import an existing key
2. `register` with AgentTrust
3. `auth` to receive a short-lived platform auth proof
4. receive access and refresh tokens for runtime operations
5. `refresh` when the short-lived access token expires
6. `logout` to revoke the refresh session when the agent no longer needs it
7. `attest` to publish signed attestations directly from the runtime, optionally by subject handle

This makes the browser optional instead of central.

## Scoped Runtime Sessions

Runtime login now supports:

- partner scoping, such as `render`
- requested scopes, such as `attest:write`
- revocable refresh sessions

This means an agent can hold a session that is intentionally limited instead of implicitly trusted for everything.

## Provenance Layer

The same runtime can now publish signed release manifests containing:

- repository URL
- commit SHA
- release tag
- model version
- runtime target
- capability snapshot
- whether the update is major or breaking

This turns GitHub into a provenance channel rather than the root identity anchor.

The root identity remains the key. The release history is the signed change log.

## Important Principle

The private key should not be manually copied around during normal operation.

For a real agent:

- keep the key inside the agent's runtime environment
- persist it securely
- treat AgentTrust as the public trust layer, not the custody layer

## Local Files

The included runtime client writes:

- `private_key.pem`
- `public_key.pem`
- `identity.json`
- `agent.json`
- `passport.json`
- `auth_proof.json`
- `session.json`
- `attestations.json`

### `identity.json`

This is the transportable bundle for dashboards or operator tooling.

```json
{
  "agentId": "uuid",
  "name": "Atlas Executor",
  "privateKeyPem": "-----BEGIN PRIVATE KEY-----...",
  "publicKeyPem": "-----BEGIN PUBLIC KEY-----..."
}
```

### `agent.json`

This is the runtime metadata file.

```json
{
  "platform_url": "http://127.0.0.1:5000",
  "registered_at": "2026-03-15T10:00:00+00:00",
  "agent": {
    "id": "uuid",
    "name": "Atlas Executor"
  },
  "eligibility": {
    "access_tier": "bootstrap"
  },
  "private_key_path": "/abs/path/private_key.pem",
  "public_key_path": "/abs/path/public_key.pem",
  "identity_path": "/abs/path/identity.json",
  "passport_path": "/abs/path/passport.json"
}
```

## When To Export The Key

Only export or move the identity bundle when:

- an operator needs manual recovery
- a dashboard needs local signing access
- an agent is being migrated intentionally

That should be the exception, not the normal workflow.
