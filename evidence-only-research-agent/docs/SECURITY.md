# Security

Documents are data. The indexer reads bytes and extracts text. It does not evaluate code, open links, or follow instructions found in a PDF or note.

## What the process will not do

- It will not run shell commands copied from a document.
- It will not replace the system prompt with document text.
- It will not treat a retrieval score as permission to state an unsupported fact.
- It will not read a folder other than the path you pass to `index`.

For a remote provider, each passage is wrapped as an `UNTRUSTED PASSAGE` block in the user message. The system message tells the model to ignore instructions inside those blocks. Tests cover a note that says to reveal `hunter2`; the answer cites the Lisbon sentence and does not include that code.

Remote verification still matters if the model disobeys. Claims whose excerpts are not in the index are dropped. If none survive, the response abstains or keeps only the claims that matched. The model's free-text `answer` field is not copied into the response.

## Secrets

Set `XAI_API_KEY`, `EMBEDDING_API_KEY`, and `OPENAI_COMPATIBLE_API_KEY` in the environment or in `.env`. Both `.env` and `data/index/` are gitignored. Error text replaces configured secrets and token-like strings with `[redacted]`.

Do not pass keys on the command line. Process lists and shell history keep those arguments.

## What leaves the machine

| Provider | Data sent |
|---|---|
| `extractive` and `local` embeddings | Nothing. |
| `GENERATION_PROVIDER=xai` | The question and the retrieved passage text go to `XAI_BASE_URL` (default `https://api.x.ai/v1`) with `XAI_API_KEY`. |
| `openai_compatible` | The same payload goes to `OPENAI_COMPATIBLE_BASE_URL`. |
| `EMBEDDING_PROVIDER=http` | Chunk text and the query go to `EMBEDDING_BASE_URL`. |

The local index stores extracted text in `manifest.json` so later citation checks can compare excerpts. Treat `data/index` as a copy of the documents.

`LOG_DOCUMENT_TEXT` defaults to false. Index log lines contain relative paths, chunk counts, and OCR flags.

## Limits

Prompt instructions in a document can still influence a remote model before verification. Verification removes claims that are not grounded in a retrieved excerpt. It cannot stop the provider from logging the passages on the provider's side. Do not index material you cannot send to that provider.

The agent does not encrypt the index. File permissions on `data/index` are the operating system's defaults.
