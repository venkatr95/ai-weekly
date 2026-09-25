# RAG Agent

Answers questions from your own PDF, TXT, and Markdown files. Every factual sentence cites a chunk that was actually retrieved. If the files do not support the question, the API says so and returns no citations.

```
Question → embedding → vector search → top chunks → grounded answer → citations
```

## Quick start

From `rag-agent`:

```powershell
py -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
uvicorn app.main:app --reload
```

Copying `.env.example` matters. It sets `VECTOR_STORE=memory`. Without that file the server default is PostgreSQL on `localhost:5432`, and startup fails if that database is not running.

Then, in another terminal from the same folder:

```powershell
py -m app.demo --pdf-only "What is the refund period?"
```

That builds a five-page refund policy, indexes it, and prints each stage. The 30-day rule is only on page 4. Chunk ids change every run. The answer looks like this:

```text
FINAL ANSWER
The refund period is 30 days. [1]
[1] refund-policy.pdf, page 4, chunk_a326850664d7
```

The log above that line is the pipeline: query embedding, the top 5 chunks with scores, the context sent onward, then the citation check.

Other sample questions, against `evaluation/corpus` plus the PDF:

```powershell
py -m app.demo "What is the difference between the refund policy and the cancellation policy?"
py -m app.demo "What is the company's annual revenue?"
```

The revenue question is not in the documents. The answer is the refusal below, with no citations.

To answer with grok instead of quoted sentences, put `XAI_API_KEY` in the environment and run:

```powershell
py -m app.demo --llm auto "What is the refund period?"
```

The demo still embeds with the local hasher, so retrieval does not depend on the embeddings endpoint. The API process is different: with a key and `EMBEDDING_PROVIDER=auto`, it uses `embed-latest`.

## API

The server listens on port 8000. Interactive docs are at http://localhost:8000/docs.

Upload the sample PDF:

```powershell
curl.exe -F "file=@sample_docs/refund-policy.pdf" http://localhost:8000/v1/documents
```

```json
{"document_id": "doc_123", "status": "indexed", "chunks": 5}
```

Ask:

```powershell
Invoke-RestMethod http://localhost:8000/v1/query -Method Post -ContentType "application/json" -Body '{"question":"What is the refund period?"}'
```

```json
{
  "answer": "The refund period is 30 days. [1]",
  "citations": [
    {"id": 1, "document": "refund-policy.pdf", "page": 4, "chunk_id": "chunk_123"}
  ]
}
```

TXT and Markdown citations have `"page": null`. PDF citations use the page the chunk was cut from. Chunks do not cross a page boundary.

Read a document back:

```powershell
Invoke-RestMethod http://localhost:8000/v1/documents/doc_123
```

```json
{"id": "doc_123", "filename": "refund-policy.pdf", "content_type": "application/pdf", "status": "indexed", "chunk_count": 5}
```

Add `"debug": true` to the query body to include the retrieved chunks, scores, and text. The same chunks are written to the server log either way.

`GET /health` reports what this process is actually using. With `.env.example` and no API key:

```json
{"status": "ok", "vector_store": "memory", "embedding_provider": "hashing", "llm_provider": "extractive"}
```

Uploads are limited to 20 MB. The extension decides the type: `.pdf`, `.txt`, `.md`, `.markdown`.

## Grounding

The model is told to use only the supplied sources. After it responds, the API still checks each sentence:

1. The citation number was in the retrieval list. A number the model invents is dropped.
2. The sentence shares terms with the question, so a true but unrelated chunk cannot answer a different question.
3. The sentence shares terms with the cited chunk, and every digit in the sentence appears in that chunk.

If nothing survives:

```json
{
  "answer": "I couldn't find sufficient information in the provided documents to answer this question.",
  "citations": []
}
```

Search returns a pool of candidates (`TOP_K` times 6, so 30 by default) and keeps the top 5 after blending cosine similarity with term overlap. If the best blended score is below the threshold, the model is not called.

## Models

Answers go through the OpenAI SDK to SpaceXAI at `https://api.x.ai/v1`.

| Role | Setting | When a key is set |
| --- | --- | --- |
| Answers | `LLM_MODEL` | `grok-4.7` |
| Reasoning | `REASONING_EFFORT` | `low`. grok-4.7 cannot turn reasoning off. |
| Embeddings | `EMBEDDING_MODEL` | `embed-latest` |

`auto` means: use the xAI endpoint when `XAI_API_KEY` is set, otherwise the offline path. The offline embedder is a local feature hash (384 dimensions). The offline answerer quotes the best supporting sentence from the retrieved chunks and never writes new facts. If `embed-latest` is unreachable at startup, the process logs a warning and uses the hasher instead. No web search or other tools are attached. The model only sees the retrieved chunks.

Tests and `evaluation/run_eval.py` always use the offline path, even if a key is present.

## PostgreSQL

```powershell
docker compose up --build
```

Compose starts `pgvector/pgvector:pg16` and the API. It forces `VECTOR_STORE=postgres` inside the container, even if your `.env` says `memory`. Document rows and embeddings live in one database. Search is cosine distance, with an HNSW index when the server can build one.

The vector column width follows the embedder: 384 for the hasher, and whatever `embed-latest` returns when that provider is active (measured once at startup). If you change embedding provider or model, delete the `pgdata` volume before starting again.

The database password in `docker-compose.yml` is a local default (`rag` / `rag`), not a production secret. Docker Desktop has to be running. This environment did not have the Docker engine up, so the compose file has not been executed here.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `XAI_API_KEY` | empty | Key for grok and for `embed-latest` |
| `VECTOR_STORE` | `postgres` in code, `memory` in `.env.example` | `postgres` or `memory` |
| `DATABASE_URL` | `postgresql+psycopg://rag:rag@localhost:5432/rag` | Used when the store is postgres |
| `CHUNK_SIZE_TOKENS` | `500` | Window length, in words and punctuation marks |
| `CHUNK_OVERLAP_TOKENS` | `100` | Must be smaller than the window |
| `TOP_K` | `5` | Chunks sent to the answerer |
| `MIN_SCORE` | `0.18` hashing, `0.35` xAI embeddings | Best blended score required before an answer is attempted |
| `VECTOR_WEIGHT` | `0.45` hashing, `0.80` xAI embeddings | Blend of cosine similarity and term overlap |
| `EMBEDDING_DIM` | `384` | Width of the hashing embedder only |
| `LLM_PROVIDER` | `auto` | `auto`, `xai`, or `extractive` |
| `EMBEDDING_PROVIDER` | `auto` | `auto`, `xai`, or `hashing` |

## Tests

```powershell
pytest
py evaluation/run_eval.py
```

The suite covers chunking, embeddings, PDF parsing, retrieval order, reranking, citation integrity, schema validation, the HTTP API, a fabricated-answer refusal, and the evaluation corpus.

`evaluation/questions.jsonl` has 16 questions: direct lookups, questions that need two documents, questions whose evidence sits in different chunks of the handbook, a citation check, and three questions the documents cannot answer (revenue, the CEO, and a Wi-Fi password).

Measured on that corpus with the offline embedder and the quoting answerer. The handbook lands in 3 chunks, so eligibility and approval are not in the same chunk. Per-question detail is in `evaluation/metrics.json`.

| Metric | Result | Target |
| --- | --- | --- |
| Retrieval recall | 100% (13/13) | ≥ 90% |
| Citation accuracy | 100% | ≥ 95% |
| Grounded answer rate | 100% (13/13) | ≥ 95% |
| Unsupported-question refusal | 100% (3/3) | 100% |

## Layout

```
app/api/            POST /v1/documents, GET /v1/documents/{id}, POST /v1/query
app/ingestion/      PDF, TXT, and Markdown parsing, chunking, embeddings
app/retrieval/      vector search and the term-overlap rerank
app/generation/     grok structured output, or quoted sentences
app/citations/      drop any citation the retrieval list does not support
app/db/             PostgreSQL + pgvector, and the in-memory store
app/demo.py         print the pipeline on the sample corpus
evaluation/         corpus, 16 questions, metric runner
sample_docs/        refund-policy.pdf, regenerated by py -m app.sample_pdf
```
