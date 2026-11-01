"""Read-only mailbox adapters. The analysis pipeline does not import this package."""

from __future__ import annotations

import json
from collections.abc import Callable
from urllib.request import Request, urlopen

Opener = Callable[[str, dict[str, str]], dict]


class IntegrationError(Exception):
    """A mailbox adapter refused the request or could not read a response."""


def default_opener(url: str, headers: dict[str, str]) -> dict:
    """Perform one HTTPS GET. There is no method argument, so this cannot POST."""
    if not url.startswith("https://"):
        raise IntegrationError("Only HTTPS URLs are allowed.")
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read()
    except Exception as exc:
        raise IntegrationError("The mailbox request failed.") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise IntegrationError("The mailbox response was not JSON.") from exc
    if not isinstance(payload, dict):
        raise IntegrationError("The mailbox response was not a JSON object.")
    return payload
