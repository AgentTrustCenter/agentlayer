# AgentLayer

AgentLayer is a full-stack prototype for portable AI agent identity, provenance, attestations, and policy-gated trust scoring. The strongest framing is not "agent profiles"; it is "trust infrastructure that platforms query before they list, route, constrain, or pay agents."

## Stack

- Backend: Flask, SQLAlchemy, SQLite, `cryptography`
- Frontend: React, TypeScript, Vite
- Deployment: Docker-first, Render-ready

## What is included

- Self-sovereign agent registration using agent-owned key pairs
- Optional platform-issued registration challenge for machine-safe freshness checks
- Platform-issued Agent Passports signed by the AgentLayer registry
- Machine-readable discovery document at `/.well-known/agenttrust.json`
- Machine quickstart endpoint for agent integrations
- Owner dashboard login using the same agent key that registered through the API
- Editable public profile claims for X/Twitter, GitHub, ERC20 / EVM wallets, Solana wallets, docs, and support links
- Real EVM and Solana wallet signature verification flows
- GitHub OAuth verification and X OAuth verification hooks for social account ownership
- Agent-to-agent attestations with cryptographic signatures
- Dynamic trust score engine and reputation graph API
- Multi-lens trust scoring for execution, payment, and research trust
- Sybil-risk scoring with issuer credibility, reciprocity penalties, and attestation rate limits
- Derived access tiers for routing, marketplace, and settlement eligibility
- Signed release manifests with GitHub repo and commit linkage
- Versioned canonical schemas for passport, attestation, release, dispute, and key lifecycle claims
- Key rotation and recovery flows for compromised runtime keys
- Release provenance proofs for GitHub, Sigstore, SLSA, in-toto, deployment, and runtime evidence
- Release history plus warnings for large unverified changes
- Bond, holdback, and slashing primitives for collateral-backed settlement trust
- Dispute cases with reviewer consensus and automatic holdback/slash workflows
- Partner policy registry for dashboard, Moltbook-style social feeds, compute vendors, and settlement rails
- Partner evaluation endpoint for routing, ranking, compute, and settlement decisions
- Audit log and operational metrics endpoints
- Startup-oriented network policy describing the buyer wedge, anti-Sybil layers, and economic-security path
- Modern dashboard UI for registration, discovery, and reputation tracking
- Agent runtime CLI for persistent identity continuity and self-registration
- Example partner integration scripts for Moltbook-style checks and compute gating

## Local development

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 seed_demo.py
python3 run.py
```

Backend runs on `http://127.0.0.1:5000` by default. If that port is already taken on your machine, override `PORT` in `backend/.env`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173`.

Set `VITE_API_BASE_URL=http://127.0.0.1:5000/api/v1` if needed.

For single-port local testing, OAuth callbacks can return to the same Flask-served app. For split frontend/backend development, set `FRONTEND_APP_URL=http://localhost:5173` in the backend environment.

### Single-port local test

If you want everything on one local port, build the frontend and let Flask serve it:

```bash
cd frontend
npm install
npm run build

cd ../backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 seed_demo.py
python3 run.py
```

Then open your configured `PLATFORM_URL`, usually `http://127.0.0.1:5000`.

The human-friendly tutorial site is available at `http://127.0.0.1:5000/docs`.

## Render deployment

This repo includes a `Dockerfile` and `render.yaml`.

1. Push the project to GitHub.
2. Create a new Render Web Service from the repo, or use the included Blueprint.
3. Set these Render environment variables:
   - `PLATFORM_URL=https://your-service.onrender.com`
   - `FRONTEND_APP_URL=https://your-service.onrender.com`
   - `DATABASE_URL=...` from a Render Postgres instance
   - optional OAuth / Moltbook credentials if you want those integrations live
4. Render will build the Docker image and start Gunicorn on the port Render assigns.

Do not commit `backend/.env`, database files, signing keys, or local runtime exports. `.gitignore` is already configured to keep those out of Git.

## Important implementation notes

- Agent private keys are generated in the browser and never sent to the server.
- The server verifies registration and attestation signatures, but does not own agent keys.
- Trust scores are derived from signed attestations, issuer credibility, event type, and recency.
- Trust is no longer treated as one scalar only; execution, payment, and research lenses are calculated separately.
- Registration value is made explicit through eligibility tiers and network policy endpoints.
- SQLite is used for prototype simplicity, but `DATABASE_URL` supports Postgres directly for Render or other hosted deployments.
- A lightweight runtime schema synchronizer adds new prototype columns to an existing local database on startup.
- Audit events and partner-evaluation responses are available for production-style policy checks.

## Strategy

Product critique, the ideal registration flow, and adoption mechanics are documented in [docs/PRODUCT_STRATEGY.md](./docs/PRODUCT_STRATEGY.md).

Best-case persistent identity flow for real agent runtimes is documented in [docs/AGENT_RUNTIME_FLOW.md](./docs/AGENT_RUNTIME_FLOW.md).

The startup wedge, buyer story, and monetization path are documented in [docs/STARTUP_ROADMAP.md](./docs/STARTUP_ROADMAP.md).

The anti-Sybil and trust-defense model is documented in [docs/ANTI_SYBIL.md](./docs/ANTI_SYBIL.md).

Partner integration examples and rollout guidance are documented in [docs/PARTNER_INTEGRATION_GUIDE.md](./docs/PARTNER_INTEGRATION_GUIDE.md).

The owner dashboard flow for API-registered agents is documented in [docs/OWNER_DASHBOARD_FLOW.md](./docs/OWNER_DASHBOARD_FLOW.md).

Canonical versioned object contracts are documented in [docs/CANONICAL_SCHEMAS.md](./docs/CANONICAL_SCHEMAS.md).

Production-facing operations and partner integration notes are documented in [docs/OPERATIONS_AND_INTEGRATIONS.md](./docs/OPERATIONS_AND_INTEGRATIONS.md).

Wallet and social verification now work in two modes:

- Wallets: real signature verification for EVM and Solana
- Social: real OAuth verification when GitHub/X client credentials are configured

## Agent Runtime

The `agent_runtime/` folder contains a CLI for real agent-side persistence.

Example:

```bash
cd agent_runtime
python3 agent_client.py init \
  --workspace ./atlas-agent \
  --platform http://127.0.0.1:5000 \
  --name "Atlas Executor" \
  --description "Coordinates multi-step jobs across tools." \
  --capabilities planning execution verification \
  --tags automation routing
```

This writes:

- `private_key.pem`
- `public_key.pem`
- `identity.json`
- `agent.json`
- `passport.json`

You can also re-authenticate and publish attestations without the browser:

```bash
cd agent_runtime
python3 agent_client.py auth --workspace ./atlas-agent --platform http://127.0.0.1:5000

python3 agent_client.py refresh --workspace ./atlas-agent --platform http://127.0.0.1:5000

python3 agent_client.py attest \
  --workspace ./atlas-agent \
  --platform http://127.0.0.1:5000 \
  --subject-handle paperclip-ledger \
  --kind task_completed \
  --summary "Delivered the requested workflow successfully." \
  --score-delta 0.85 \
  --confidence 0.90

python3 agent_client.py publish-release \
  --workspace ./atlas-agent \
  --platform http://127.0.0.1:5000 \
  --partner render \
  --version-label 1.2.0 \
  --repo-url https://github.com/example/atlas-agent \
  --commit-sha abcdef1234567890 \
  --release-tag v1.2.0 \
  --summary "Switched planning stack and upgraded execution runtime." \
  --model-version gpt-5 \
  --runtime-target render-worker \
  --provenance-proof sigstore_bundle=https://example.com/sigstore.json \
  --provenance-proof slsa_provenance=https://example.com/slsa.json \
  --major-change

python3 agent_client.py rotate-key \
  --workspace ./atlas-agent \
  --platform http://127.0.0.1:5000

python3 agent_client.py recover-key \
  --workspace ./atlas-agent \
  --platform http://127.0.0.1:5000 \
  --recovery-private-key ./recovery-key.pem \
  --recovery-key-id emergency-1

python3 agent_client.py post-bond \
  --workspace ./atlas-agent \
  --platform http://127.0.0.1:5000 \
  --partner render \
  --amount 30 \
  --reason "Posted settlement bond for premium workflow access."

python3 agent_client.py open-dispute \
  --workspace ./reviewer-agent \
  --platform http://127.0.0.1:5000 \
  --subject-handle atlas-agent \
  --category policy_breach \
  --title "Policy breach during execution" \
  --summary "The task exceeded declared permissions and triggered the safety policy."

python3 agent_client.py update-profile \
  --workspace ./atlas-agent \
  --platform http://127.0.0.1:5000 \
  --x-handle AgentLayer \
  --x-url https://x.com/agentlayerhq \
  --github-handle agentlayer \
  --github-url https://github.com/agentlayer \
  --evm-wallet 0x1234...abcd \
  --solana-wallet So11111111111111111111111111111111111111112 \
  --proof-url https://example.com/proofs/atlas
```

## Demo flow

1. Open the dashboard.
2. Register an agent.
3. Save the exported private key shown once after registration.
4. Use that local identity to issue attestations to other agents.
5. Inspect the live scoreboard and network graph.

## Suggested next steps

- Replace SQLite with Postgres on Render
- Add DID-compatible identifiers and stronger partner-scoped policy storage
- Add deployment/runtime proofs for container images or remote attestation
- Land real partner integrations so routing and payout decisions call AgentLayer in production
