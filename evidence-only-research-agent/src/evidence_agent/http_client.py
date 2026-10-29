"""Small JSON HTTP client used by optional remote providers."""

from __future__ import annotations

import json
from urllib import error, request

from evidence_agent.errors import ProviderError
from evidence_agent.security import scrub_text


def urllib_transport(url: str, payload: dict, headers: dict, timeout: float, secrets: list[str | None] | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        message = _provider_message(detail, exc.code)
        raise ProviderError(scrub_text(message, secrets)) from exc
    except error.URLError as exc:
        raise ProviderError(
            scrub_text(
                f"Could not reach the model provider at {url}. {exc.reason}",
                secrets,
            )
        ) from exc
    except TimeoutError as exc:
        raise ProviderError(scrub_text(f"The model provider timed out after {timeout} seconds.", secrets)) from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderError("The model provider returned a response that is not JSON.") from exc
    if not isinstance(parsed, dict):
        raise ProviderError("The model provider returned an unexpected response.")
    return parsed


def _provider_message(body: str, status: int) -> str:
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        error_body = parsed.get("error")
        if isinstance(error_body, dict) and error_body.get("message"):
            return f"Model provider returned HTTP {status}: {error_body['message']}"
        if isinstance(error_body, str):
            return f"Model provider returned HTTP {status}: {error_body}"
    if status in {401, 403}:
        return f"Model provider rejected the API key (HTTP {status}). Check the key in the environment."
    return f"Model provider returned HTTP {status}."
