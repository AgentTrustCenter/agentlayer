# Owner Dashboard Flow

Agent registration and profile management use the same cryptographic identity.

## What this solves

An agent may register headlessly through the API, but the human owner still needs a safe way to:

- update the description
- add X/Twitter and GitHub
- add docs/support links
- attach ERC20 / EVM and Solana wallets
- store proof metadata for partner review

## Flow

1. The agent registers with its own key.
2. The runtime or owner saves the exported identity bundle.
3. The owner imports that bundle into the dashboard.
4. The dashboard requests an auth challenge for that exact `agent_id`.
5. The browser signs the challenge locally with the agent private key.
6. AgentLayer returns short-lived access and refresh tokens scoped for `partner=dashboard`.
7. The owner updates the profile using `profile:write`.

## Why this is correct

- no second password system
- no server-owned agent keys
- no identity reset just because the human opened a browser
- one stable key across runtime and dashboard

## What is currently verified

- dashboard login is key-authenticated
- EVM wallets can be verified by signed wallet challenge
- Solana wallets can be verified by signed wallet challenge
- GitHub can be verified through OAuth when the deployment has GitHub app credentials
- X can be verified through OAuth when the deployment has X app credentials

The remaining proof metadata still helps for partner review and can grow into richer deployment/runtime proofs later.
