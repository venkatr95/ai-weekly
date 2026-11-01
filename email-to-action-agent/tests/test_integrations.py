"""Mailbox adapters stay read-only and do not run without an explicit token."""

import base64
import json
from pathlib import Path
from urllib.request import Request

import pytest

from integrations import IntegrationError, default_opener
from integrations.gmail import GmailClient
from integrations.outlook import OutlookClient


def test_missing_token_does_not_call_the_opener(monkeypatch):
    monkeypatch.delenv("GMAIL_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("OUTLOOK_ACCESS_TOKEN", raising=False)

    def opener(url, headers):
        raise AssertionError(url)

    with pytest.raises(IntegrationError):
        GmailClient(opener=opener)
    with pytest.raises(IntegrationError):
        OutlookClient(opener=opener)


def test_clients_expose_no_write_methods():
    forbidden = {"send", "delete", "modify", "trash", "update", "post", "patch", "send_reply"}
    for cls in (GmailClient, OutlookClient):
        names = {name for name in dir(cls) if not name.startswith("_")}
        assert forbidden.isdisjoint(names)


def test_gmail_reads_with_an_injected_opener():
    calls = []

    def opener(url, headers):
        calls.append((url, headers["Authorization"]))
        if "format=full" in url:
            return {
                "id": "abc",
                "snippet": "unused",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "Sarah <sarah@example.com>"},
                        {"name": "Subject", "value": "Notes"},
                    ],
                    "mimeType": "text/plain",
                    "body": {
                        "data": base64.urlsafe_b64encode(b"Hi Alex,\n\nPlease send the notes.").decode()
                    },
                },
            }
        return {"messages": [{"id": "abc"}]}

    client = GmailClient(token="test-token", opener=opener)
    assert client.list_messages(query="launch")[0]["id"] == "abc"
    text = client.to_email_text(client.get_message("abc"))
    assert "From: Sarah <sarah@example.com>" in text
    assert "Please send the notes." in text
    assert all(url.startswith("https://gmail.googleapis.com/") for url, _auth in calls)
    assert all(auth == "Bearer test-token" for _url, auth in calls)


def test_outlook_reads_with_an_injected_opener():
    def opener(url, headers):
        assert headers["Authorization"] == "Bearer outlook-token"
        assert url.startswith("https://graph.microsoft.com/")
        if "/me/messages/msg1" in url:
            return {
                "subject": "Notes",
                "from": {"emailAddress": {"name": "Sarah", "address": "sarah@example.com"}},
                "toRecipients": [{"emailAddress": {"name": "Alex", "address": "alex@example.com"}}],
                "receivedDateTime": "2026-11-01T09:00:00Z",
                "body": {"contentType": "text", "content": "Please send the notes."},
            }
        return {"value": [{"id": "msg1"}]}

    client = OutlookClient(token="outlook-token", opener=opener)
    assert client.list_messages()[0]["id"] == "msg1"
    text = client.to_email_text(client.get_message("msg1"))
    assert "From: Sarah <sarah@example.com>" in text
    assert "Please send the notes." in text
    assert "Date: 2026-11-01T09:00:00Z" in text


def test_default_opener_is_get_only(monkeypatch):
    captured = {}

    class _Response:
        def read(self):
            return b'{"messages": []}'

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_urlopen(request: Request, timeout=30):
        captured["method"] = request.get_method()
        captured["url"] = request.full_url
        return _Response()

    monkeypatch.setattr("integrations.urlopen", fake_urlopen)
    payload = default_opener("https://example.test/messages", {"Accept": "application/json"})
    assert payload == {"messages": []}
    assert captured["method"] == "GET"
    assert json.loads("{}") == {}


def test_pipeline_does_not_import_integrations():
    source = Path(__file__).resolve().parents[1] / "src" / "email_to_action" / "pipeline.py"
    text = source.read_text(encoding="utf-8")
    assert "import integrations" not in text
    assert "from integrations" not in text
