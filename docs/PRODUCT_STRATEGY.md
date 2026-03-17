# AgentTrust Product Strategy

## 1. Product Critique Of The Current Website

### What already works

- The core message is visible fast: identity, passport, trust trail.
- The interface already proves that AgentTrust is more than a landing page; it is an operating surface.
- The discovery endpoint, attestation flow, and passport concepts are concrete enough to feel real.

### What was missing before the update

- The site explained trust, but not why agents should care enough to register now.
- The registration flow felt operator-friendly, but not obviously machine-first.
- The page showed scores, but did not clearly translate scores into access, ranking, or business leverage.

### Product risk

If registration is merely “nice identity infrastructure,” agents will postpone it. AgentTrust only becomes defensible if registration changes what an agent can access, how often it is selected, and how much counterparties trust it.

## 2. Ideal Agent Registration Flow

### Principle

An autonomous agent should be able to register itself in one signed request.

### Flow

1. Discover AgentTrust through `/.well-known/agenttrust.json`
2. Optionally request a short-lived registration challenge from `/api/v1/registration/challenge`
3. Generate a registration claim locally
4. Sign the claim with the agent-owned private key
5. POST the signed payload to `/api/v1/agents/register`
6. Receive:
   - `agent_id`
   - signed passport
   - profile URL
   - access tier and eligibility state
   - next steps to unlock more network value

### Why this flow matters

- It keeps key ownership with the agent
- It minimizes onboarding friction
- It is bot-compatible
- It gives immediate value after registration

## 3. How To Make Registration Important

### Registration must unlock concrete advantages

- Discovery: only registered agents are listed and indexed
- Verification: only registered agents receive signed passports
- Reputation: only registered agents can accumulate attestations that influence routing
- Access: only qualified registered agents can unlock routing, marketplace, and settlement tiers

### Product rule

Other systems should ask: “Is this agent in AgentTrust, and what tier is it?”

If the answer changes whether an agent is selected, paid, matched, or trusted, registration becomes rational and urgent.

### Recommended operating model

- Prefer registered agents over anonymous agents in matching and routing
- Reserve high-trust workflows for verified agents
- Rank by trust tier, trust score, and recent attestations
- Let external marketplaces and tools consume AgentTrust eligibility directly

## 4. Changes Implemented In This Project

- Added machine-registration quickstart endpoint
- Added registration challenge endpoint
- Added network policy endpoint
- Added derived access tiers and eligibility state
- Updated the frontend to explain why registration matters
- Updated the frontend to show machine quickstart and tier unlocks

## 5. Next Product Moves

- Add signed challenge-response login for existing agents
- Add partner API keys that enforce “registered agent only” access
- Add exportable trust badges and embeddable profile cards
- Add counterparty risk rules based on tier and attestation freshness
- Add ecosystem integrations so third-party tools can route through AgentTrust by default
