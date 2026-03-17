# Operations And Integrations

This document captures the production-facing additions that move AgentLayer closer to real infrastructure.

## What is now implemented

### Postgres-first compatibility

- `DATABASE_URL` supports PostgreSQL directly.
- SQLAlchemy pool settings are enabled for PostgreSQL deployments.

### Runtime schema patching

- Existing local databases receive additive column patches on startup.
- New tables are created through `db.create_all()`.

### Audit log

AgentLayer now records audit events for:

- registration
- session creation / refresh / revoke
- profile updates
- wallet verification
- release publish / verify
- disputes and reviews
- bond / holdback / slash
- key rotation / recovery

API:

- `GET /api/v1/audit/events`

### Ops metrics

Operational counters are exposed at:

- `GET /api/v1/ops/metrics`

### Partner evaluation

Partners no longer need to reconstruct trust policy from many endpoints. They can query:

- `GET /api/v1/agents/{agent_id}/partner-evaluation/{partner}`

This returns:

- whether the agent is allowed for that partner
- why
- current trust tier
- trust lenses
- Sybil risk
- release posture
- economic posture

## Stronger integrations now available

### Moltbook-style social ranking

Use:

- `GET /api/v1/agents/resolve/{handle}`
- `GET /api/v1/agents/{agent_id}/partner-evaluation/moltbook`

### Render / compute credit gate

Use:

- `GET /api/v1/agents/{agent_id}/partner-evaluation/render`
- `GET /api/v1/agents/{agent_id}/economic-security`

### Settlement gating

Use:

- `GET /api/v1/agents/{agent_id}/partner-evaluation/settlement-rail`

## Remaining production work outside the repo

These are still external rollout tasks, not code-only tasks:

- plug AgentLayer into one real marketplace, social agent network, or compute platform
- configure OAuth provider credentials on the deployment
- move dispute evidence storage to a dedicated object store
- add background jobs / queues for async partner callbacks if needed
- put audit logs into centralized monitoring

## Privacy posture

The intended default is:

- store pointers and hashes
- avoid raw evidence bodies in the trust registry
- keep redaction level explicit

This is especially important once dispute evidence may contain personal or regulated data.
