import json
import sys
import urllib.request


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python3 settlement_partner_gate.py <base_url> <agent_id>")
        return 1

    base_url = sys.argv[1].rstrip("/")
    agent_id = sys.argv[2]
    agent = fetch_json(f"{base_url}/api/v1/agents/{agent_id}")["agent"]
    decision = fetch_json(f"{base_url}/api/v1/agents/{agent_id}/partner-evaluation/settlement-rail")

    print(
        json.dumps(
            {
                "agent": agent["handle"],
                "allowed_for_settlement": decision["allowed"],
                "reason": decision["reason"],
                "trust_score": agent["trust_score"],
                "payment_trust": agent.get("trust_lenses", {}).get("payment"),
                "sybil_risk_score": agent.get("sybil_risk_score"),
                "economic_security": agent.get("economic_security"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
