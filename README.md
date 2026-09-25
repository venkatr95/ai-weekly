# ai_projects

A collection of local Python AI agents and tools. Each project is self-contained with its own `venv/`, `.env`, and `PRD.md`.

## Projects

| # | Project | What it does |
|---|---|---|
| 1 | [structured-output-agent](./structured-output-agent/) | Converts natural-language support messages into validated `SupportTicket` objects using Pydantic schema enforcement and LLM retry logic |
| 2 | [personal-rag-assistant](./personal-rag-assistant/) | Local RAG chatbot over personal documents (PDF, TXT, MD) with conversational memory and incremental indexing |
| 3 | [sanskrit-tts](./sanskrit-tts/) | Local Sanskrit text-to-speech with Indic Parler-TTS — generates Devanāgarī recitation audio as `.mp3` from a notebook or script |
| 4 | [rag-agent](./rag-agent/) | FastAPI RAG service over PDF, TXT, and Markdown. Answers from retrieved chunks only, with citations, and refuses when the documents do not support the question |

## Style

Most projects follow the same flat script style — see [`.agents/skills/local-python-project-style/SKILL.md`](.agents/skills/local-python-project-style/SKILL.md) for the conventions. `rag-agent` is the exception: it is a FastAPI service with the layout in its own README.

- Flat file structure — no `app/` or `src/` packages
- `PRD.md` as the living product document
- One `*_core.py` module + one or two thin entry-point scripts
- `python extract.py` / `python rag.py` — no servers
- Multi-provider LLM support via `LLM_PROVIDER` env var (Gemini, Anthropic, OpenAI, Grok)

## Quick start (projects 1–3)

```bash
cd <project>
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # add your API key
python <entry>.py --interactive
```

[rag-agent](./rag-agent/) is a FastAPI service, not one of these scripts. Its setup, query API, and evaluation numbers are in [rag-agent/README.md](./rag-agent/README.md).
