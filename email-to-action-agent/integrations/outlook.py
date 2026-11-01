"""Read-only Microsoft Graph adapter for Outlook. It cannot send, delete, or modify messages."""

from __future__ import annotations

import os
import re
from urllib.parse import quote, urlencode

from integrations import IntegrationError, Opener, default_opener

_LIST = "https://graph.microsoft.com/v1.0/me/messages"
_SELECT = "id,subject,from,toRecipients,ccRecipients,receivedDateTime,body,bodyPreview"


class OutlookClient:
    def __init__(self, token: str | None = None, opener: Opener | None = None) -> None:
        resolved = os.environ.get("OUTLOOK_ACCESS_TOKEN") if token is None else token
        if not resolved or not str(resolved).strip():
            raise IntegrationError(
                "Outlook access requires OUTLOOK_ACCESS_TOKEN. Authorization is explicit, and access is read-only."
            )
        self._token = str(resolved).strip()
        self._opener = opener or default_opener

    def list_messages(self, query: str = "", max_results: int = 10) -> list[dict]:
        if max_results < 1:
            raise IntegrationError("max_results must be at least 1.")
        params = {"$top": max_results, "$select": _SELECT}
        if query:
            params["$search"] = f'"{query}"'
        payload = self._get(f"{_LIST}?{urlencode(params)}")
        messages = payload.get("value") or []
        if not isinstance(messages, list):
            raise IntegrationError("Unexpected Outlook list response.")
        return [item for item in messages if isinstance(item, dict)]

    def get_message(self, message_id: str) -> dict:
        self._check_id(message_id)
        params = urlencode({"$select": _SELECT})
        return self._get(f"{_LIST}/{quote(message_id)}?{params}")

    def to_email_text(self, payload: dict) -> str:
        sender = (payload.get("from") or {}).get("emailAddress") or {}
        name = sender.get("name")
        address = sender.get("address")
        lines: list[str] = []
        if name or address:
            parts = [str(name)] if name else []
            if address:
                parts.append(f"<{address}>")
            lines.append("From: " + " ".join(parts))
        recipients = _addresses(payload.get("toRecipients"))
        copied = _addresses(payload.get("ccRecipients"))
        if recipients:
            lines.append("To: " + ", ".join(recipients))
        if copied:
            lines.append("Cc: " + ", ".join(copied))
        if payload.get("subject"):
            lines.append(f"Subject: {payload['subject']}")
        if payload.get("receivedDateTime"):
            lines.append(f"Date: {payload['receivedDateTime']}")
        body = payload.get("body") or {}
        content = str(body.get("content") or "")
        if str(body.get("contentType") or "").lower() == "html":
            content = _strip_html(content)
        if not content:
            content = str(payload.get("bodyPreview") or "")
        lines.extend(["", content])
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
        if not message_id or any(char in message_id for char in " /\\?#"):
            raise IntegrationError("message_id is not valid.")


def _addresses(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    found: list[str] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        email_address = item.get("emailAddress") or {}
        if not isinstance(email_address, dict):
            continue
        label = email_address.get("name") or email_address.get("address")
        if label:
            found.append(str(label))
    return found


def _strip_html(value: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"[ \t]+", " ", text).strip()
