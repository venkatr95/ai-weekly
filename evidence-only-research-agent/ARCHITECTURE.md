# Architecture

The agent is a single-process Python application. `cli.py` parses commands. `ResearchPipeline` indexes a folder and answers one question at a time. Components under `src/evidence_agent/` can be constructed with fake embedders and generators, which is how the tests avoid the network.

```text
documents -> discover/extract -> chunk -> embed -> local index
question -> retrieve -> draft claims -> verify citations -> markdown or JSON
```

## Components

| Module | Responsibility |
|---|---|
| `ingestion.py` | Recursive discovery of `.pdf`, `.txt`, `.md`, and `.markdown`. Extraction keeps page text. Corrupt, empty, and scanned files are recorded and do not stop the run. |
| `chunking.py` | Whitespace-token windows, default 800 tokens with 120 tokens of overlap. A chunk belongs to one file. Character spans remember which PDF page each slice came from. Chunk ids are a SHA-256 of the path, ordinal, and text. |
| `embeddings.py` | `local` fits hashed TF-IDF on the chunk texts. `http` posts to an OpenAI-compatible `/embeddings` endpoint. Unseen query features are ignored so unknown words do not hit a random bucket. |
| `vector_store.py` | Writes `manifest.json` and `embeddings.npy` atomically. Loading a truncated or mismatched index raises `CorruptIndexError`. |
| `retrieval.py` | Hybrid score: half cosine similarity, half query-term overlap. The score only decides which passages are shown to the answer step. |
| `answer_generation.py` | The extractive provider splits the question, drops subquestions whose terms are missing from the index, and quotes sentences that overlap the subquestion. Opposite polarity sentences with a high term overlap become an unresolved conflict. The xAI and OpenAI-compatible providers send only the retrieved passages and must return JSON. |
| `citation_verification.py` | Rebuilds the user-facing answer. An excerpt must occur in the indexed chunk, the page must match, numbers in the claim must occur in the excerpt, and enough claim terms must occur in the excerpt. Free-form model prose is discarded. |
| `security.py` | System prompt and the untrusted-passage wrapper used for remote models. Secret redaction for provider errors. |
| `evaluation.py` | Scores the gold file in `examples/questions.json`. |

## Index lifecycle

Indexing walks the folder, skips hidden files and unsupported types, and reuses extracted chunks when the file hash and chunk settings are unchanged. Local embeddings are refit every time, because TF-IDF weights depend on the whole corpus. HTTP embeddings reuse stored vectors for unchanged chunk ids.

A removed file disappears on the next index. `--rebuild` ignores the previous index. Changing `CHUNK_SIZE`, `CHUNK_OVERLAP`, the embedding provider, or the embedding width requires re-extraction or a rebuild. Asking against an index built with different embedding settings fails with a message that says to rebuild.

The manifest stores chunk text. That is required to check citations later. Logs do not include chunk text unless `LOG_DOCUMENT_TEXT=true`.

## Answer rules

1. Decompose on question marks and on `and` before another question word.
2. If too many question terms never appear in the index, record `missing_documents` and do not invent an answer.
3. Otherwise retrieve passages and keep sentences whose weighted term overlap clears `SUPPORT_THRESHOLD` (default 0.55) and sit near the best sentence.
4. A supported claim's excerpt is that sentence. The page is the page span that contains it, or null for text and Markdown.
5. Sentences with opposite polarity and enough shared terms are returned together. `resolved` is always false.
6. If no claim and no conflict survives verification, `abstained` is true.
7. Remote generation gets one retry when every claim fails verification. An HTTP or authentication failure is an error, not an abstention.

The public `answer` string is composed from the verified claims, conflicts, and gaps. It does not copy the model's free-text answer.

## Remote model

When `GENERATION_PROVIDER=xai`, the client calls `POST {XAI_BASE_URL}/chat/completions` with model `grok-4.7` by default. The base URL default is `https://api.x.ai/v1`. The request uses `response_format: json_object` and retries once without that field if the provider rejects it. Document text is placed in the user message, inside `UNTRUSTED PASSAGE` blocks. It is not placed in the system message.

xAI's collections API documents an embedding model named `grok-embedding-small`. This project does not call that collections API. Neural embeddings are used only if you point `EMBEDDING_PROVIDER=http` at an endpoint you have verified.

## What is intentionally out of scope

Web browsing, fine-tuning, OCR, multi-user serving, and editing source files are not implemented. Conflict resolution is not implemented: the agent reports both sides.
