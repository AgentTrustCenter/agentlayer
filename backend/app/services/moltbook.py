from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class MoltbookVerificationError(Exception):
    pass


def verify_moltbook_identity(*, token: str, app_key: str, verify_url: str, timeout: float = 8.0) -> dict[str, Any]:
    normalized_token = "".join(token.split())
    if not normalized_token:
        raise MoltbookVerificationError("Moltbook identity token is empty.")
    if not app_key.strip():
        raise MoltbookVerificationError(
            "Moltbook verification is not configured. Set MOLTBOOK_APP_KEY in backend/.env or export it before starting the server."
        )

    request_body = json.dumps({"token": normalized_token}).encode("utf-8")
    request = Request(
        verify_url,
        data=request_body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Moltbook-App-Key": app_key,
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore").strip()
        raise MoltbookVerificationError(f"Moltbook verification failed with status {exc.code}. {detail}".strip()) from exc
    except URLError as exc:
        raise MoltbookVerificationError(f"Could not reach Moltbook verification service: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise MoltbookVerificationError("Moltbook returned an invalid JSON response.") from exc

    if not payload.get("success") or not payload.get("valid"):
        raise MoltbookVerificationError(payload.get("error") or "Moltbook identity token is invalid or expired.")

    agent = payload.get("agent")
    if not isinstance(agent, dict) or not agent.get("id"):
        raise MoltbookVerificationError("Moltbook response did not include a valid agent profile.")

    return payload
