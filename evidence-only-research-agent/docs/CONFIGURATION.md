# Configuration

Settings come from the process environment. A `.env` file in the current directory is loaded only for variables that are not already set. `.env` is gitignored. Start from `.env.example`.

Never put a real key in source code.

## Generation

| Variable | Default | Meaning |
|---|---|---|
| `GENERATION_PROVIDER` | `extractive` | `extractive`, `xai`, or `openai_compatible`. |
| `XAI_API_KEY` | empty | Required for `xai`. Create a key in the [xAI console](https://console.x.ai). |
| `XAI_MODEL` | `grok-4.7` | Model id sent to the chat completions API. |
| `XAI_BASE_URL` | `https://api.x.ai/v1` | API origin. The client posts to `{base}/chat/completions`. |
| `OPENAI_COMPATIBLE_BASE_URL` | empty | Required for `openai_compatible`. |
| `OPENAI_COMPATIBLE_API_KEY` | empty | Sent as a bearer token. Use any non-empty placeholder if the local server ignores it. |
| `OPENAI_COMPATIBLE_MODEL` | empty | Model name the server expects. |
| `REQUEST_TIMEOUT_SECONDS` | `60` | HTTP timeout. |

`extractive` does not call a model. Claims are sentences copied from retrieved passages.

`xai` sends the question and the retrieved passages to xAI. The system prompt tells the model to treat passage text as data. After the response, citation verification drops claims whose excerpts are not in the index or do not overlap the claim. See [SECURITY.md](SECURITY.md).

`openai_compatible` uses the same request shape against a server you choose. A local example:

```bash
GENERATION_PROVIDER=openai_compatible
OPENAI_COMPATIBLE_BASE_URL=http://127.0.0.1:11434/v1
OPENAI_COMPATIBLE_API_KEY=ollama
OPENAI_COMPATIBLE_MODEL=llama3.2
```

That server is not bundled. If it is unreachable, `ask` exits with an error instead of guessing.

## Embeddings

| Variable | Default | Meaning |
|---|---|---|
| `EMBEDDING_PROVIDER` | `local` | `local` or `http`. |
| `EMBEDDING_DIMENSIONS` | `384` | Width of the stored vectors. |
| `EMBEDDING_BASE_URL` | empty | Required for `http`, without a trailing path. The client posts to `{base}/embeddings`. |
| `EMBEDDING_API_KEY` | empty | Bearer token for that endpoint. |
| `EMBEDDING_MODEL` | empty | Model field in the embedding request. |

The local provider is hashed TF-IDF. It does not download a model. It is weak on paraphrases. Rebuild the index after changing provider or dimensions. Querying an index with mismatched settings fails on purpose.

xAI documents `grok-embedding-small` for its collections API. This project does not call that API. Use `EMBEDDING_PROVIDER=http` only after you confirm the endpoint returns one vector per input of length `EMBEDDING_DIMENSIONS`.

## Indexing and retrieval

| Variable | Default | Meaning |
|---|---|---|
| `INDEX_DIR` | `data/index` | Where the manifest and vectors are stored. |
| `CHUNK_SIZE` | `800` | Whitespace tokens per chunk. Minimum 20. |
| `CHUNK_OVERLAP` | `120` | Overlap in whitespace tokens. Must be smaller than `CHUNK_SIZE`. |
| `RETRIEVAL_K` | `6` | Passages kept per retrieval. |
| `SIMILARITY_THRESHOLD` | `0.15` | Minimum hybrid retrieval score, from 0 to 1. |
| `SUPPORT_THRESHOLD` | `0.55` | Minimum stemmed-term overlap before a sentence can become a claim. |
| `LOG_DOCUMENT_TEXT` | `false` | Reserved. Index logs record paths and counts, not passage text. |

CLI flags override the index directory, chunk size, chunk overlap, retrieval count, and similarity threshold for that command.

Changing chunk size or overlap causes the next index to re-extract, because the stored chunks would no longer match.
