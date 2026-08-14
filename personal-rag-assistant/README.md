# Personal RAG Assistant with Memory

A chatbot that knows your documents. Upload PDFs, notes, or text files and chat with them. It cites its sources, remembers conversation context, only re-indexes files that changed, and can run as a CLI or a web UI.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

This pulls in `sentence-transformers`, which pulls in `torch` — it's a large download, give it a few minutes.

Set your API key:

```bash
cp .env.example .env
# open .env and paste your key into ANTHROPIC_API_KEY= (or your chosen provider's key)
```

The scripts load `.env` automatically at startup (via `python-dotenv`, called from each entry point) — no need to `export` it yourself.

### Choosing an LLM provider

By default, chat runs on Anthropic Claude. To use a different provider, set `LLM_PROVIDER` in `.env`:

| `LLM_PROVIDER` | Default model | API key env var |
|---|---|---|
| `anthropic` (default) | `claude-sonnet-5` | `ANTHROPIC_API_KEY` |
| `openai` | `gpt-5.1` | `OPENAI_API_KEY` |
| `gemini` | `gemini-3-pro` | `GOOGLE_API_KEY` |
| `grok` | `grok-4.1` | `XAI_API_KEY` |

Only the API key for your chosen provider is required. To pin a specific model instead of the default, set `LLM_MODEL` (e.g. `LLM_MODEL=gpt-5.1-mini`). Provider selection is shared by all three entry points via `rag_core.get_llm()`.

Add documents:

```bash
mkdir -p docs
cp ~/path/to/your/notes.pdf docs/
cp ~/path/to/your/research.md docs/
```

Supported types: `.pdf`, `.txt`, `.md`.

## Run it

### CLI

```bash
python rag.py
```

First run downloads the `all-MiniLM-L6-v2` embedding model (~90MB) and builds `chroma_db/`. Answers are followed by a `Sources:` line listing which document(s) they were drawn from.

### Web UI

```bash
streamlit run streamlit_app.py
```

Chat in the browser, see per-answer source citations in an expandable panel, and reindex or clear the conversation from the sidebar.

### Daily digest

```bash
python daily_digest.py
```

Summarizes what's new or changed across your documents since the last time it ran (tracked in `digest_state.json`). Useful wired into cron / Task Scheduler for a periodic "what's new in my notes" readout.

## How indexing works

Every run computes a SHA-256 hash of each file in `docs/` and compares it against `index_manifest.json`. Only new or changed files are re-embedded and written to the vector store; unchanged files are skipped, and files removed from `docs/` have their chunks dropped automatically. This means you can drop new files into `docs/` and re-run any of the three entry points — no full rebuild needed.

## Project files

| File | Purpose |
|---|---|
| `rag_core.py` | Shared indexing, retrieval, and chain-building logic used by all three entry points |
| `rag.py` | CLI chat loop |
| `streamlit_app.py` | Web chat UI |
| `daily_digest.py` | Standalone "what's new" summary script |
| `docs/` | Drop your source documents here (gitignored in practice — see below) |
| `chroma_db/` | Local persisted vector store (auto-created) |
| `index_manifest.json` | Tracks per-file content hashes for incremental indexing (auto-created) |
| `digest_state.json` | Tracks the last digest run timestamp (auto-created) |

If you put this under git, add `docs/`, `chroma_db/`, `*.json` state files, and `.env` to `.gitignore` — they're local data and secrets, not source.

## Notes on the model

Chat runs on whichever provider `LLM_PROVIDER` selects (Anthropic Claude by default — see "Choosing an LLM provider" above). Retrieval uses a local embedding model (`sentence-transformers/all-MiniLM-L6-v2`) regardless of chat provider — documents and their embeddings never leave your machine except for the final chat completion call to whichever LLM API you've configured.

## Extending further

Ideas not implemented here, in roughly ascending order of effort:

- **External source connectors** (Notion, Google Docs) — auto-ingest documents from those APIs into `docs/` on a schedule, reusing `sync_vectorstore()` as-is.
- **Cloud-persisted vector store** (e.g. Turso) — swap `get_vectorstore()` in `rag_core.py` for a remote-backed store if you need this running across multiple machines. Not needed for single-machine use.
