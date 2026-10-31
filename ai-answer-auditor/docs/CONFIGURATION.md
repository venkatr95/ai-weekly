# Configuration

The default configuration runs entirely on the machine. Copy `.env.example` to `.env` only if you change a setting. `.env` is gitignored. The loader does not override variables that are already set in the environment.

| Variable | Default | Purpose |
| --- | --- | --- |
| `AUDITOR_PROVIDER` | `heuristic` | `heuristic` or `xai`. |
| `XAI_API_KEY` | empty | Required for `xai`. Read from the environment. Not written into reports. |
| `XAI_MODEL` | `grok-4.7` | Model id sent to the xAI Responses API. |
| `XAI_BASE_URL` | `https://api.x.ai/v1` | API origin. The client calls `/responses`. |
| `AUDITOR_LOG_SOURCES` | `0` | Source text is not logged at info level. Leave this off for confidential documents. |

The CLI flag `--provider heuristic` or `--provider xai` overrides `AUDITOR_PROVIDER` for that command.

## Heuristic provider

No network call. The same answer and sources produce the same report. Use this for tests, the bundled benchmark, and any audit you need to reproduce.

## xAI provider

The client sends one JSON request per extraction and one per verification:

- Endpoint: `POST {XAI_BASE_URL}/responses`
- Model: `XAI_MODEL`
- `store` is false, so the request asks the provider not to retain the conversation
- The claim and the passages are separate fields. Passages are labeled as untrusted data
- Web search is not enabled

The provider's response is not accepted as proof. Quotations must occur in the extracted sources, and the deterministic numeric checks in `claim_verifier.py` can overrule the model. Details are in [SECURITY.md](SECURITY.md) and [../ARCHITECTURE.md](../ARCHITECTURE.md).

xAI data handling is described by xAI at [https://docs.x.ai](https://docs.x.ai). Do not send documents to that API unless that handling is acceptable for the documents. The heuristic provider does not send them anywhere.
