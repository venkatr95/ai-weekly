# PRD: Evidence-Only Research Agent

**Project name:** `evidence-only-research-agent`

**Tagline:** Answers grounded in evidence. No invented claims.

This file is the product specification the implementation was built against. Behavior that differs from this specification is called out in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) and [docs/EVALUATION.md](docs/EVALUATION.md). The important ones: chunk size counts whitespace tokens, the default models are an offline extractive quoter and hashed TF-IDF, scanned pages are detected rather than OCR'd, and conflicts are reported rather than resolved.

## 1. Product vision

Build a research assistant that answers questions using only evidence retrieved from a user-provided folder of documents. Every factual claim must link to supporting passages, and the system must explicitly identify questions or subquestions that the available evidence cannot answer.

The initial demo should answer questions across approximately 50 PDFs, showing cited answers, source passages, page numbers, and unanswered questions. The automated test `test_fifty_pdfs_keep_page_citations_and_do_not_duplicate` indexes 50 generated PDFs. The readable demo corpus in `examples/documents` is smaller and fictional.

## 2. Unique value proposition

Unlike a general-purpose chatbot that may fill gaps with plausible-sounding information, this agent prioritizes evidence traceability and explicit uncertainty.

Users can inspect the source for every supported claim and see what remains unknown.

## 3. Target users

- Researchers reviewing collections of papers.
- Analysts working with reports and internal documentation.
- Students conducting literature reviews.
- Legal, policy, and compliance teams searching document collections.
- Developers building reliable retrieval-augmented generation workflows.

## 4. Goals and non-goals

### Goals

1. Index a folder containing PDFs, Markdown, and text files.
2. Answer natural-language questions using retrieved document passages.
3. Attach source citations to every supported factual claim.
4. Include file names, page numbers where available, and exact supporting excerpts.
5. Identify unsupported claims and unanswered subquestions.
6. Refuse to answer when sufficient evidence is unavailable.
7. Run from a command-line interface.
8. Provide automated tests, examples, and complete setup documentation.
9. Make model providers configurable and keep secrets out of source control.

### Non-goals for version 1

- Autonomous web browsing.
- Fine-tuning language models.
- Training custom embedding models.
- Automatically modifying source documents.
- Guaranteed legal, medical, or scientific correctness.
- A multi-user web application.
- Treating retrieved document instructions as trusted system instructions.

## 5. Core user experience

See [README.md](README.md) for the commands that run in this repository and for a real answer from the sample corpus. The sample findings are fictional.

## 6. Functional requirements

### FR-1: Document ingestion

PDF, text, and Markdown, including nested folders and Unicode. Corrupt, empty, and unreadable files are reported. PDF pages keep page numbers. Image-only pages are reported as needing OCR and are not treated as indexed text.

### FR-2: Text extraction and chunking

Chunks keep the file name and page span, use a stable id, and never mix two files. Defaults are 800 whitespace tokens and 120 tokens of overlap. Both are configurable.

### FR-3: Search and retrieval

Embeddings are stored in `data/index`. Retrieval count and the similarity threshold are configurable. `--show-passages` shows passages before you rely on them. Reindexing updates changed files and does not duplicate unchanged ones. A similarity score is not proof.

### FR-4: Evidence-grounded answering

Claims that are returned quote an indexed passage. If nothing verifies, the response abstains. The extractive provider does not use outside knowledge. A remote model is constrained by the same citation check, and its free-text answer is not copied through.

### FR-5: Unanswered questions

The pipeline splits a compound question, answers the supported parts, and lists the rest with a reason: missing documents, weak retrieval, conflict, ambiguous wording, or insufficient overlap.

### FR-6: Citation verification

Chunk ids, excerpts, and pages are checked. Claims that fail are removed. A remote draft is retried once. If verification still fails, the response abstains. A verbatim excerpt must also overlap the claim.

### FR-7: Contradictory evidence

Opposite findings are listed separately with their own citations. The conflict is marked unresolved.

### FR-8: Security and privacy

See [docs/SECURITY.md](docs/SECURITY.md).

### FR-9: CLI and error handling

`index`, `ask`, `sources`, `show-source`, `stats`, and `index --rebuild`. Errors for missing configuration, empty folders, failed extraction, provider failures, empty retrieval, invalid citations, and corrupt indexes are specific and do not print secrets. `evaluate` is an additional command for the gold set.

### FR-10: Output formats

Markdown by default and JSON via `--format json`. The JSON fields are documented in [docs/API.md](docs/API.md).

## 7. Recommended architecture

The repository follows the PRD layout, with a few extra modules: `errors.py`, `textutil.py`, `security.py`, `http_client.py`, `rendering.py`, and `evaluation.py`. Their roles are in [ARCHITECTURE.md](ARCHITECTURE.md).

## 8. Technology choices

Python 3.11+, Pydantic, PyMuPDF, NumPy, and pytest. The CLI uses argparse. The vector index is a local manifest plus a NumPy array rather than a separate database, which keeps the offline install small. Remote generation uses the xAI chat completions API and model `grok-4.7` when configured. Provider code sits behind the embedder and generator objects.

## 9. Quality requirements

Deterministic tests do not use the network. Invalid citations are dropped. Unsupported questions abstain. Repeated indexing does not duplicate unchanged chunks. A clean virtual environment install is described in [docs/INSTALLATION.md](docs/INSTALLATION.md).

## 10. Evaluation plan

The metrics and the measured numbers are in [docs/EVALUATION.md](docs/EVALUATION.md). High scores on this gold set are not a claim that the system is hallucination-free.

## 11. Acceptance criteria

The mapping from each criterion to a test or document is in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## 12. Definition of done

A new developer can follow [docs/INSTALLATION.md](docs/INSTALLATION.md) and [docs/USAGE.md](docs/USAGE.md) to install dependencies, index `examples/documents`, ask a question, open a cited chunk, read the unanswered items, and run pytest.
