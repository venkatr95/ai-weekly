"""Read-only Gmail adapter. It lists and reads messages. It cannot send, delete, or modify them."""

from __future__ import annotations

import base64
import os
import re
from urllib.parse import quote, urlencode

from integrations import IntegrationError, Opener, default_opener

_LIST = "https://gmail.googleapis.com/gmail/v1/users/me/messages"


class GmailClient:
    def __init__(self, token: str | None = None, opener: Opener | None = None) -> None:
        resolved = os.environ.get("GMAIL_ACCESS_TOKEN") if token is None else token
        if not resolved or not str(resolved).strip():
            raise IntegrationError(
                "Gmail access requires GMAIL_ACCESS_TOKEN. Authorization is explicit, and access is read-only."
            )
        self._token = str(resolved).strip()
        self._opener = opener or default_opener

    def list_messages(self, query: str = "", max_results: int = 10) -> list[dict]:
        if max_results < 1:
            raise IntegrationError("max_results must be at least 1.")
        params = urlencode({"maxResults": max_results, "q": query})
        payload = self._get(f"{_LIST}?{params}")
        messages = payload.get("messages") or []
        if not isinstance(messages, list):
            raise IntegrationError("Unexpected Gmail list response.")
        return [item for item in messages if isinstance(item, dict)]

    def get_message(self, message_id: str) -> dict:
        self._check_id(message_id)
        return self._get(f"{_LIST}/{quote(message_id)}?format=full")

    def to_email_text(self, payload: dict) -> str:
        headers = {
            str(item.get("name", "")).lower(): str(item.get("value", ""))
            for item in (payload.get("payload") or {}).get("headers") or []
            if isinstance(item, dict)
        }
        body = _plain_text(payload.get("payload") or {}) or str(payload.get("snippet") or "")
        lines: list[str] = []
        for key, label in (("from", "From"), ("to", "To"), ("cc", "Cc"), ("subject", "Subject"), ("date", "Date")):
            if headers.get(key):
                lines.append(f"{label}: {headers[key]}")
        lines.extend(["", body])
        return "\n".join(lines).strip()

    def _get(self, url: str) -> dict:
        payload = self._opener(
            url,
            {"Authorization": f"Bearer {self._token}", "Accept": "application/json"},
        )
        if not isinstance(payload, dict):
            raise IntegrationError("The mailbox response was not a JSON object.")
        return payload

    @staticmethod
    def _check_id(message_id: str) -> None:
        if not message_id or not re.fullmatch(r"[A-Za-z0-9_-]+", message_id):
            raise IntegrationError("message_id is not valid.")


def _plain_text(part: dict) -> str:
    mime = str(part.get("mimeType") or "")
    data = (part.get("body") or {}).get("data")
    if mime == "text/plain" and isinstance(data, str):
        return _decode(data)
    if mime == "text/html" and isinstance(data, str):
        return _strip_html(_decode(data))
    for child in part.get("parts") or []:
        if isinstance(child, dict):
            found = _plain_text(child)
            if found:
                return found
    return ""


def _decode(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8", errors="replace")
    except (ValueError, UnicodeError):
        return ""


def _strip_html(value: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"[ \t]+", " ", text).strip()
