# Evidence-only research agent

Answers grounded in a folder of documents. Every supported finding quotes a stored passage. If the documents do not support a question, the agent says so.

The default provider runs offline. It does not fill gaps from model knowledge. A remote model is optional, and its claims still have to match the index.

## Quick start

Python 3.11 or newer is required. On Windows, use `py -3` when `python` is not on `PATH`.

```bash
py -3 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
py -3 examples/build_sample_pdfs.py
py -3 cli.py index ./examples/documents
py -3 cli.py ask "What evidence supports the effectiveness of Intervention X, and what long-term benefits are reported?"
py -3 -m pytest
```

Run `pytest` from this directory. The sample papers are fictional.

Indexing the sample folder reports one scanned PDF. That file has no text layer, so it is not searchable:

```text
OCR: scans/empty_scan.pdf: No text layer on pages [1]. This looks like a scan and requires OCR. Those pages were not indexed as searchable text.
```

## What an answer looks like

This is the real output of the command above against `examples/documents` with the default extractive provider:

```markdown
**Answer**

The documents support 1 cited statement. Some parts of the question remain unanswered by the available evidence.

**Supported findings**

1. **Finding:** The reported evidence supports the effectiveness of Intervention X.

   - Source: `study_a_rivera_2024.pdf`, page 2
   - Supporting passage: "The reported evidence supports the effectiveness of Intervention X."
   - Evidence status: Supported
   - Verification: verified

**Unanswered questions**

- What long-term benefits are reported?
  - Reason: missing_documents
  - Detail: No indexed passage contains these question terms: long, term, benefits.

**Conflicts**

None.
```

A question the corpus does not cover abstains. A question where Rivera 2024 and Halvorsen 2024 disagree is returned as two cited positions with the conflict left unresolved.

## Commands

```bash
py -3 cli.py index ./documents
py -3 cli.py index ./documents --rebuild
py -3 cli.py ask "Your research question"
py -3 cli.py ask "Your research question" --format json
py -3 cli.py ask "Your research question" --show-passages
py -3 cli.py sources
py -3 cli.py show-source <chunk-id>
py -3 cli.py stats
py -3 cli.py evaluate
```

`--show-passages` prints retrieved text and scores. A score only ranks passages. It is not proof.

## Providers

| Provider | Network | Role |
|---|---|---|
| `extractive` (default) | No | Quotes sentences from retrieved passages. |
| `xai` | Yes, `https://api.x.ai/v1` | Asks `grok-4.7` for JSON claims. Passages leave the machine. Invalid citations are dropped. |
| `openai_compatible` | Whatever base URL you set | Same check, for a local server such as Ollama. |
| Embeddings `local` (default) | No | Hashed TF-IDF. Not a neural semantic model. |
| Embeddings `http` | Yes | OpenAI-compatible `POST /embeddings`. |

Set `XAI_API_KEY` only in the environment or a gitignored `.env`. See [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## Tests and evaluation

`py -3 -m pytest` runs 33 tests without network access. The suite includes a generated folder of 50 PDFs, page-number checks, abstention, conflicting sources, citation rejection, and a prompt-injection sentence that must not be obeyed.

`py -3 cli.py evaluate` rebuilds a temporary index of `examples/documents` and scores `examples/questions.json`. The latest local run is in [examples/evaluation_results.json](examples/evaluation_results.json) and [docs/EVALUATION.md](docs/EVALUATION.md). Those perfect scores are for this small synthetic set. They do not mean the system is hallucination-free.

## Documentation

- [docs/INSTALLATION.md](docs/INSTALLATION.md)
- [docs/CONFIGURATION.md](docs/CONFIGURATION.md)
- [docs/USAGE.md](docs/USAGE.md)
- [docs/API.md](docs/API.md)
- [docs/EVALUATION.md](docs/EVALUATION.md)
- [docs/SECURITY.md](docs/SECURITY.md)
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
- [PRD.md](PRD.md)

## Limits

- The extractive provider needs overlapping words. A paraphrase with no shared terms can abstain even when a person would see a connection.
- Local embeddings are hashed TF-IDF, not a trained semantic model.
- Scanned pages are detected and skipped. OCR is not run.
- Conflicting sources are reported and not reconciled.
- Citation checks catch invented excerpts and poorly overlapping claims. They do not prove that a quote was used fairly, and they do not make the source documents true.
- This is not a legal, medical, or scientific authority.
