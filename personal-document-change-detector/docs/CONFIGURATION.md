# Configuration

The default configuration runs entirely on the machine. Create a local `.env` only if you change a setting. `.env` is gitignored. The loader does not override variables that are already set in the environment.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DETECTOR_PROVIDER` | `heuristic` | `heuristic` or `xai`. |
| `XAI_API_KEY` | empty | Required for `xai`. Read from the environment. Not written into reports. |
| `XAI_MODEL` | `grok-4.7` | Model id sent to the xAI Responses API. |
| `XAI_BASE_URL` | `https://api.x.ai/v1` | API origin. The client calls `/responses`. |
| `DETECTOR_LOG_DOCUMENTS` | `0` | Document text is not logged at info level. Leave this off for confidential documents. |

The CLI flag `--provider heuristic` or `--provider xai` overrides `DETECTOR_PROVIDER` for that command. The browser page has the same control. It starts on `heuristic` even when `DETECTOR_PROVIDER` is `xai`, and it sends change excerpts to xAI only after that provider is selected and a comparison is run.

## Heuristic provider

No network call. The same document pair produces the same report. Use this for tests, the bundled employment example, and any comparison you need to reproduce.

## xAI provider

The client may send one JSON request with the verified change excerpts:

- Endpoint: `POST {XAI_BASE_URL}/responses`
- Model: `XAI_MODEL`
- `store` is false, so the request asks the provider not to retain the conversation
- Change excerpts are labeled as untrusted data
- Web search is not enabled

The model may refine titles, explanations, importance, and recommendations. Deterministic diffs still decide *what* changed. Quotations must appear in the extracted document text. Details are in [SECURITY.md](SECURITY.md) and [../ARCHITECTURE.md](../ARCHITECTURE.md).

xAI data handling is described by xAI at [https://docs.x.ai](https://docs.x.ai). Do not send documents to that API unless that handling is acceptable for the documents. The heuristic provider does not send them anywhere.
