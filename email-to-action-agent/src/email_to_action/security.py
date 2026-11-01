"""Boundaries for untrusted email text."""

from __future__ import annotations

import re

from email_to_action.errors import EmailActionError

_KEY_PATTERN = re.compile(
    r"\b(?:sk|xai|bearer|api|token)[-_][A-Za-z0-9_\-]{8,}\b",
    re.IGNORECASE,
)
_ASSIGNMENT = re.compile(
    r"(?im)^(?:xai_api_key|api_key|authorization|bearer|password)\s*[:=]\s*\S+"
)


def check_size(text: str, limit: int) -> None:
    if len(text) > limit:
        raise EmailActionError(f"Email is {len(text)} characters, above the limit of {limit}.")


def scrub(text: str) -> str:
    """Redact secret-shaped strings. Evidence stored on tasks is left verbatim."""

    redacted = _KEY_PATTERN.sub("[redacted]", text)
    return _ASSIGNMENT.sub("[redacted]", redacted)
