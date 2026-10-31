# ai_projects

A collection of local Python AI agents and tools. Each project is self-contained with its own `venv/`, `.env`, and `PRD.md`.

## Projects

| # | Project | What it does |
|---|---|---|
| 1 | [structured-output-agent](./structured-output-agent/) | Converts natural-language support messages into validated `SupportTicket` objects using Pydantic schema enforcement and LLM retry logic |
| 2 | [personal-rag-assistant](./personal-rag-assistant/) | Local RAG chatbot over personal documents (PDF, TXT, MD) with conversational memory and incremental indexing |
| 3 | [sanskrit-tts](./sanskrit-tts/) | Local Sanskrit text-to-speech with Indic Parler-TTS — generates Devanāgarī recitation audio as `.mp3` from a notebook or script |
| 4 | [rag-agent](./rag-agent/) | FastAPI RAG service over PDF, TXT, and Markdown. Answers from retrieved chunks only, with citations, and refuses when the documents do not support the question |
| 5 | [evidence-only-research-agent](./evidence-only-research-agent/) | Answers a question from a local folder of PDF, Markdown, and text files. Every finding quotes a stored passage, or the agent abstains |
| 6 | [ai-answer-auditor](./ai-answer-auditor/) | Checks an AI-generated answer against the sources supplied with it. Splits the answer into claims, assigns a status to each one, and quotes the supporting or contradicting passage |

## Style

Projects 1–3 follow the flat script style in [`.agents/skills/local-python-project-style/SKILL.md`](.agents/skills/local-python-project-style/SKILL.md).

- Flat file structure — no `app/` or `src/` packages
- `PRD.md` as the living product document
- One `*_core.py` module + one or two thin entry-point scripts
- `python extract.py` / `python rag.py` — no servers
- Multi-provider LLM support via `LLM_PROVIDER` env var (Gemini, Anthropic, OpenAI, Grok)

[rag-agent](./rag-agent/) is a FastAPI service. [evidence-only-research-agent](./evidence-only-research-agent/) and [ai-answer-auditor](./ai-answer-auditor/) are `src/` packages with a `cli.py`. Each of those three documents its own layout in its README.

## Quick start (projects 1–3)

```bash
cd <project>
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # add your API key
python <entry>.py --interactive
```

[rag-agent](./rag-agent/) setup, the query API, and evaluation numbers are in [rag-agent/README.md](./rag-agent/README.md).

[evidence-only-research-agent](./evidence-only-research-agent/) indexes a folder, then answers from that index:

```bash
cd evidence-only-research-agent
py -3 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
py -3 cli.py index ./examples/documents
py -3 cli.py ask "What evidence supports the effectiveness of Intervention X?"
```

[ai-answer-auditor](./ai-answer-auditor/) checks a generated answer against source files. The default checker runs offline:

```bash
cd ai-answer-auditor
py -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python cli.py audit --answer examples/answer.txt --sources examples/sources
```
