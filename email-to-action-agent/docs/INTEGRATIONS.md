# Integrations

Gmail and Outlook adapters are optional. `analyze()` does not import them. Paste the email, or fetch one message yourself and pass the text to `analyze()`.

Both clients are read-only:

- A token is required. The environment variables are `GMAIL_ACCESS_TOKEN` and `OUTLOOK_ACCESS_TOKEN`. You can also pass `token=` to the constructor.
- Without a token, the client raises `IntegrationError` and does not open a connection.
- `list_messages` and `get_message` use HTTPS GET.
- `to_email_text` turns the fetched payload into plain text. Missing fields stay missing.
- There is no send, delete, modify, or trash method.
- The returned text is not analyzed until you call `analyze()`. The draft that call produces is still not sent.

```python
from integrations.gmail import GmailClient
from email_to_action import analyze

client = GmailClient()  # reads GMAIL_ACCESS_TOKEN
chosen = client.list_messages(query="subject:launch", max_results=5)
text = client.to_email_text(client.get_message(chosen[0]["id"]))
action = analyze(text)
```

Outlook uses `OutlookClient` and `OUTLOOK_ACCESS_TOKEN`. The list and message calls go to Microsoft Graph `GET /me/messages`.

IMAP is not connected. An IMAP adapter would follow the same rules: explicit credentials, read-only commands, a chosen message, and no send or delete from this tool.

Tests inject an opener and do not call Gmail or Graph. The default opener exists for a real token and uses `method="GET"` only.
