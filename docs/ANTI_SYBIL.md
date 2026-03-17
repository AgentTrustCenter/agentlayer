# AgentTrust Anti-Sybil Model

## Problem

If any actor can cheaply create many new agent identities and have them attest to each other, reputation becomes noise. A useful agent trust layer must make registration cheap enough for honest onboarding but make influence expensive enough that spam and coordinated manipulation do not dominate the network.

## Principle

Cheap registration is acceptable.

Cheap influence is not.

That means AgentTrust should not treat every new key or every signed attestation as equally meaningful.

## Why Pure Proof-of-Work Is Not Enough

A small computational puzzle or a fixed action cost can reduce low-effort spam, but it is not sufficient as the main trust primitive.

Problems with a pure proof-of-work model:

- strong attackers can pay the compute bill
- honest small operators may be penalized more than large attackers
- compute cost proves effort, not truth
- it does not solve reciprocal attestation rings or coordinated collusion

## Recommended Defense Stack

### 1. Identity continuity

The same key persists over time. New identities begin with low influence.

### 2. Weighted attestations

Attestations should be weighted by:

- issuer trust
- issuer age and continuity
- partner verification
- context and interaction type
- reciprocity and ring behavior

### 3. Release provenance

Major changes should create visible release warnings until independently verified.

### 4. Policy tiers and rate limits

New agents can onboard quickly, but cannot immediately unlock:

- large score impact
- marketplace preference
- production access
- settlement rights

### 5. Economic security

For high-impact actions, use capital risk rather than only compute waste:

- refundable bonds
- payout holdbacks
- slashable collateral

## Best Use Of Costly Actions

Costly actions still have value, but as a narrow friction layer:

- rate-limit registration bursts
- discourage challenge abuse
- slow low-value spam

They are weaker than bonded mechanisms for anything that changes routing, ranking, or money movement.

## Product Implication

AgentTrust should eventually distinguish:

1. cheap onboarding
2. slow trust growth
3. expensive influence
4. capital-backed high-trust actions

That structure is much more robust than trying to solve all abuse with a single hard puzzle per attestation.
