import json
import sys
import urllib.request


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python3 render_compute_gate.py <base_url> <agent_id>")
        return 1

    base_url = sys.argv[1].rstrip("/")
    agent_id = sys.argv[2]
    payload = fetch_json(f"{base_url}/api/v1/agents/{agent_id}/economic-security")
    agent = payload["agent"]
    posture = payload["bond_account"] or {}
    partner_decision = fetch_json(f"{base_url}/api/v1/agents/{agent_id}/partner-evaluation/render")

    decision = {
        "grant_priority_compute": bool(
            partner_decision["allowed"]
            and posture.get("net_bonded_balance", 0) >= 10
            and not posture.get("active_holdback", False)
        ),
        "reason": f"{partner_decision['reason']}: require marketplace-class trust plus bonded balance and no active holdback.",
    }
    print(json.dumps({"agent": agent["handle"], "decision": decision, "posture": posture, "trust_lenses": agent.get("trust_lenses", {})}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
