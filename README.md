# ai_projects

A collection of local Python AI agents and tools. Each project is self-contained with its own `venv/`, `.env`, and `PRD.md`.

## Projects

| # | Project | What it does |
|---|---|---|
| 1 | [structured-output-agent](./structured-output-agent/) | Converts natural-language support messages into validated `SupportTicket` objects using Pydantic schema enforcement and LLM retry logic |
| 2 | [personal-rag-assistant](./personal-rag-assistant/) | Local RAG chatbot over personal documents (PDF, TXT, MD) with conversational memory and incremental indexing |

## Style

All projects follow the same flat script style — see [`.agents/skills/local-python-project-style/SKILL.md`](.agents/skills/local-python-project-style/SKILL.md) for the conventions.

- Flat file structure — no `app/` or `src/` packages
- `PRD.md` as the living product document
- One `*_core.py` module + one or two thin entry-point scripts
- `python extract.py` / `python rag.py` — no servers
- Multi-provider LLM support via `LLM_PROVIDER` env var (Gemini, Anthropic, OpenAI, Grok)

## Quick start (any project)

```bash
cd <project>
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # add your API key
python <entry>.py --interactive
```
