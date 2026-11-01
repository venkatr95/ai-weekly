# Configuration

Version 1 has no environment variables and no API key.

`Settings` in `email_to_action.config` holds two fields:

| Field | Default | Meaning |
| --- | --- | --- |
| `max_chars` | `1000000` | Maximum email size, in characters |
| `provider` | `heuristic` | The only extractor. There is no model provider in this version |

Pass a `Settings` object to `analyze()` when a test or a caller needs a smaller limit. The CLI uses the defaults.

Logs from `--verbose` include counts of messages and tasks. They do not include the email body.
