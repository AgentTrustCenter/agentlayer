import json
import sys
import urllib.request


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python3 moltbook_partner_check.py <base_url> <agent_handle>")
        return 1

    base_url = sys.argv[1].rstrip("/")
    handle = sys.argv[2]
    agent = fetch_json(f"{base_url}/api/v1/agents/resolve/{handle}")["agent"]
    decision = fetch_json(f"{base_url}/api/v1/agents/{agent['id']}/partner-evaluation/moltbook")
    disputes = fetch_json(f"{base_url}/api/v1/agents/{agent['id']}/disputes")["disputes"]

    print(
        json.dumps(
            {
                "agent": handle,
                "eligible_for_promotion": decision["allowed"],
                "reason": decision["reason"],
                "trust_score": agent["trust_score"],
                "trust_lenses": agent.get("trust_lenses", {}),
                "sybil_risk_score": agent.get("sybil_risk_score"),
                "access_tier": agent["access_tier"],
                "open_disputes": len([item for item in disputes if item["status"] == "open"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
