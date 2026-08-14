# PRD: Personal RAG Assistant with Memory

**Owner:** Venkat Madhavan
**Status:** v1 implemented (see § Implementation Status)
**Last updated:** 2026-08-04 (multi-provider LLM support added)

## 1. Problem Statement

Knowledge workers accumulate personal knowledge across scattered, disconnected surfaces — PDFs, markdown notes, saved research, meeting docs. There is no single place to *ask* questions across all of it in natural language, and no tool that gets smarter about your own material the more you use it. Existing note apps support search-by-keyword, not reasoning-by-meaning; existing chat assistants don't have access to your private documents or memory of your prior conversations with them.

## 2. Goal

Ship a local, single-user chatbot that:
- Ingests a folder of personal documents (PDF, TXT, MD) into a local vector store.
- Answers natural-language questions grounded in that content (RAG).
- Retains conversational memory across a session so follow-up questions work without re-stating context.
- Runs entirely on the user's machine (no account, no cloud DB) except for the LLM call itself.

## 3. Non-Goals (v1)

- No multi-user / team access or auth.
- No live sync with Notion/Google Docs/other SaaS sources.
- No persistent cross-session memory of *conversations* (only cross-session memory of *documents*, via the vector store). Each run starts a fresh chat memory.
- No cloud-hosted vector store — stays single-machine.

> Two items originally listed as non-goals — a web UI and source citations — were pulled into v1 during implementation once they proved low-effort on top of the shared retrieval core. See § Implementation Status.

## 4. Target User

A single technical user (the builder themself, or a similarly technical person) comfortable running a Python CLI script locally. Not designed for non-technical end users in v1.

## 5. User Stories

1. As a user, I want to drop PDFs/notes into a `docs/` folder and have them automatically indexed, so I don't need to manually manage a database.
2. As a user, I want to ask a question and get an answer synthesized from *my* documents, not the model's general knowledge, so answers are grounded and relevant to me.
3. As a user, I want to ask follow-up questions ("how does that connect to X?") without repeating context, so the conversation feels natural.
4. As a user, I want this to run fully locally except for the LLM API call, so my documents aren't uploaded to a third-party vector DB.

## 6. Functional Requirements

| # | Requirement | Priority |
|---|---|---|
| 1 | Load `.pdf`, `.txt`, `.md` files from a local `docs/` folder | P0 |
| 2 | Chunk documents (recursive character splitting, ~1000 chars, 200 overlap) | P0 |
| 3 | Embed chunks locally (no external embedding API) and persist to a local vector store | P0 |
| 4 | Retrieve top-k relevant chunks per query | P0 |
| 5 | Generate answers via Claude, grounded in retrieved chunks | P0 |
| 6 | Maintain in-session conversational memory (last N exchanges) so follow-ups resolve correctly | P0 |
| 7 | CLI chat loop with clean exit (`quit`/`exit`/`q`) | P0 |
| 8 | Re-running the script should not need to re-embed unchanged documents from scratch each time (persisted store) | P1 — **done**, via content-hash manifest |
| 9 | Show which source document(s) an answer was drawn from | P1 — **done** |
| 10 | Auto-ingest new files dropped into `docs/` without a manual re-run | P2 — **partially done**: any entry point picks up new/changed files on its next run via the same incremental-index path; no filesystem watcher, so nothing runs *between* invocations |
| 11 | Let the user pick their LLM provider (Anthropic, OpenAI, Gemini, Grok) instead of hardcoding one | P1 — **done**, via `LLM_PROVIDER`/`LLM_MODEL` env vars |

## 7. Success Metrics

Since this is a personal-use tool, "success" is qualitative and usage-based rather than growth-based:

- **Retrieval relevance**: informal spot-check — top-k chunks returned are actually relevant to the query for a sample of test questions.
- **Answer groundedness**: model doesn't hallucinate facts absent from the source docs (spot-checked, not automated in v1).
- **Time-to-first-answer**: from `python rag.py` to first usable answer, under ~60s for a small doc set (excludes first-run model download).
- **Habitual use**: the real signal — does the builder keep reaching for this instead of manually re-reading old notes/PDFs.

## 8. Technical Approach (as scoped)

- **Language/runtime**: Python 3.10+ (verified 3.12), local virtualenv.
- **Orchestration**: LangChain (`ConversationalRetrievalChain`, `return_source_documents=True`).
- **Embeddings**: local `sentence-transformers` model (`all-MiniLM-L6-v2`) via `HuggingFaceEmbeddings` — no embedding API cost or upload.
- **Vector store**: ChromaDB (via `langchain_chroma`), persisted locally to `./chroma_db`.
- **LLM**: Multi-provider via `rag_core.get_llm()`, selected by `LLM_PROVIDER` env var (default `anthropic`). Supported: Anthropic Claude (`claude-sonnet-5`), OpenAI (`gpt-5.1`), Google Gemini (`gemini-3-pro`), xAI Grok (`grok-4.1`); `LLM_MODEL` overrides the default model for whichever provider is selected. Each provider's langchain integration reads its own API key env var (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `XAI_API_KEY`). No `temperature` override — left at each provider's default rather than the originally-planned `temperature=0.3`, since Claude Sonnet 5 rejects non-default sampling parameters (400 error) and a shared default keeps behavior consistent across providers.
- **Memory**: `ConversationBufferWindowMemory`, last 10 exchanges, in-process only (not persisted across runs).
- **Config**: API key via `.env`, auto-loaded at import time via `python-dotenv` (no manual `export` needed).
- **Incremental indexing**: SHA-256 content hash per file, tracked in `index_manifest.json`. Only new/changed files are re-embedded; removed files have their chunks dropped via a metadata-filtered delete. Shared by all three entry points (`rag.py`, `streamlit_app.py`, `daily_digest.py`) through `rag_core.py`.

### Known technical debt / risks to flag
- `rag_core.sync_vectorstore()` reaches into Chroma's private `_collection.delete(where=...)` API to drop stale chunks — there's no public LangChain method for a metadata-filtered delete on the currently pinned `langchain_chroma` version. Worth re-checking if the LangChain Chroma integration adds a public equivalent.
- No dedupe/versioning if the same document content is saved under two different filenames in `docs/` — each is indexed and cited separately.
- Daily digest excerpts are capped at ~6000 characters per file (`MAX_CHARS_PER_FILE` in `daily_digest.py`) to bound the prompt; a very large single new document will be summarized from a truncated excerpt, not its full text.
- PDF citations show a page number; `.txt`/`.md` citations show only the filename (no natural "page" concept for LangChain's `TextLoader`).

## 9. Rollout Plan

Single-phase local rollout — no staged release, no feature-flagging, since this is a single-user local tool:
1. Setup instructions (venv, deps, `.env`) verified end-to-end on a clean machine.
2. `docs/` folder + first-run smoke test with 2-3 sample documents of mixed type (PDF + MD).
3. Manual QA pass: ask 5-10 questions spanning single-doc lookup, cross-doc synthesis, and a multi-turn follow-up, confirm memory carries context correctly.

## 10. Implementation Status

Shipped, beyond original v1 scope — the low-effort future-work items were pulled forward because they shared the same retrieval core:

| Item | Status | Where |
|---|---|---|
| Source citations | ✅ Done | `rag_core.format_sources()`; surfaced in CLI (`Sources:` line) and web UI (expander) |
| Streamlit web UI | ✅ Done | `streamlit_app.py` — chat UI, sidebar reindex button, per-answer citations |
| Auto-ingest (incremental, not filesystem-watching) | ✅ Done | `rag_core.sync_vectorstore()` — hash-based, runs at the start of every entry point |
| Daily digest | ✅ Done | `daily_digest.py` — summarizes files changed since last run, standalone/cron-able |
| Multi-provider LLM support (OpenAI, Gemini, Grok, in addition to Anthropic) | ✅ Done | `rag_core.get_llm()`, selected via `LLM_PROVIDER`/`LLM_MODEL` env vars; used by both chat (`build_chain`) and the digest |
| External source connectors (Notion) | ❌ Not built | Needs real API credentials to build against; deferred rather than built untested |
| Cloud-persisted vector store (e.g. Turso) | ❌ Not built | Explicitly out of scope while this stays single-machine (see Non-Goals) |

## 11. Future Work (post-v1, not committed)

1. **External source connectors** (Notion) — expands what "your documents" means beyond local files. `rag_core.sync_vectorstore()` is already structured to accept documents from anywhere that can produce a file on disk in `docs/`, so a connector's job is just "pull remote content into `docs/` on a schedule."
2. **True filesystem watching** (e.g. `watchdog`) instead of re-sync-on-invocation — only worth it if the assistant becomes a long-running process rather than invoked per-question.
3. **Cloud-persisted vector store** (e.g., Turso) — only relevant if this needs to run across multiple machines/devices; explicitly deprioritized while this stays single-machine/local.

## 12. Open Questions

- Is cross-*session* conversation memory (not just document memory) actually needed, or is per-session memory sufficient given this is a personal tool used in bursts? (Streamlit's `st.session_state` currently resets on browser refresh, same limitation as the CLI resetting per-invocation.)
- What's the expected document volume at steady state (10s vs. 100s vs. 1000s of files)? Incremental indexing removes the full-re-embed cost, but Chroma's own scaling characteristics at high document counts haven't been tested.
- Local-only embeddings are a deliberate privacy/cost tradeoff — confirm this constraint still holds before considering hosted embedding APIs for quality improvements.
