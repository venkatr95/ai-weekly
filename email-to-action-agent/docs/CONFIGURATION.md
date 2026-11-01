# Configuration

The analyzer does not need an API key. Email text stays on this machine.

`Settings` in `email_to_action.config` holds two fields:

| Field | Default | Meaning |
| --- | --- | --- |
| `max_chars` | `1000000` | Maximum email size, in characters |
| `provider` | `heuristic` | The only extractor. It does not call a model |

Pass a `Settings` object to `analyze()` when a test or a caller needs a smaller limit. The CLI uses the defaults.

These arguments are per call, not environment variables:

| Argument | CLI flag | Default | Meaning |
| --- | --- | --- | --- |
| `received_at` | `--received-at` | none | ISO-8601 timestamp for messages that have no Date header |
| `tone` | `--tone` | `professional` | `professional`, `friendly`, `concise`, or `formal` |
| `include_reply` | `--no-reply` | reply included | Skip the draft when the flag is set |

Optional mailbox tokens are read only by `integrations/`, and only when you construct a client. Copy `.env.example` to `.env` if you store them locally. `.env` is gitignored. The analyzer does not load `.env` and does not read the tokens.

| Variable | Client |
| --- | --- |
| `GMAIL_ACCESS_TOKEN` | `integrations.gmail.GmailClient` |
| `OUTLOOK_ACCESS_TOKEN` | `integrations.outlook.OutlookClient` |

A missing token raises `IntegrationError` before any network call. The clients send HTTPS GET requests only.

Logs from `--verbose` include counts of messages and tasks. They do not include the email body.
