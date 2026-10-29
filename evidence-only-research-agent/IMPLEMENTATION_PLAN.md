# Implementation plan

The milestones in the PRD are implemented in this repository. Status below is the state of the code, not a promise about documents the user has not indexed.

## Milestone 1 — Foundations

Done. The package layout, settings, schemas, CLI, discovery, PDF and text extraction, chunking, and their tests are in place. Page spans are kept. Empty, corrupt, and image-only PDFs are reported.

## Milestone 2 — Search

Done. The default index is hashed TF-IDF stored as NumPy vectors plus a JSON manifest. `sources`, `show-source`, and `stats` read that index. Reindexing an unchanged folder does not duplicate chunks. `--rebuild` replaces it. An HTTP embedding client exists behind `EMBEDDING_PROVIDER=http` and is covered with a fake transport.

## Milestone 3 — Evidence-grounded answers

Done. The extractive generator emits sentence-level claims, unanswered subquestions, and citations. The verifier checks chunk ids, verbatim excerpts, pages, and term overlap. Failed claims are removed. If nothing remains, the response abstains. JSON and Markdown both come from the verified object.

## Milestone 4 — Reliability

Done. Polarity heuristics surface direct disagreements and leave them unresolved. Hedged limitation sentences are not treated as a competing finding. Document text is untrusted data. API keys are read from the environment and scrubbed from provider errors. End-to-end tests use the extractive provider and fake remote transports.

## Milestone 5 — Documentation and demo

Done. Setup, configuration, usage, API, evaluation, security, and troubleshooting docs are in `docs/`. `examples/documents` is a fictional corpus. `examples/questions.json` is the gold set. `examples/evaluation_results.json` is the measured run documented in `docs/EVALUATION.md`. A clean virtual environment installed `requirements.txt` and passed `pytest` on Python 3.12.10.

## Acceptance mapping

| Criterion | Where it is demonstrated |
|---|---|
| Index 50 PDFs | `tests/test_retrieval.py` builds 50 PDFs, indexes them, and checks a page-2 citation. |
| PDF file and page metadata | Same test, plus the Rivera and Okonkwo questions in the gold set. |
| Markdown and text | Sample corpus and `tests/test_ingestion.py`. |
| Claim-level citations | Gold set and CLI `--format json`. |
| Citations checked against stored text | `tests/test_citation_verification.py`. |
| Abstention | `q_unanswerable` and `tests/test_abstention.py`. |
| Partial answers | `q_partial`. |
| Contradictions stay unresolved | `q_conflict` and `tests/test_conflicting_evidence.py`. |
| Repeat indexing | Reuse counts in the 50-PDF test and `test_incremental_index_does_not_duplicate`. |
| JSON schema | `AnswerResponse` fields asserted in `tests/test_end_to_end.py`. |
| Tests | `py -3 -m pytest` from this directory. |
| Docs and a runnable demo | `README.md`. |

## Known limits of this implementation

- "Token" in chunk settings means a whitespace-separated word, not a model tokenizer piece.
- Local retrieval is lexical. Paraphrases can miss.
- The support check is overlap of stemmed content words plus number matching. A citation can be topically related and still be a weak argument. The check rejects claims that introduce numbers or mostly new words.
- Conflict detection looks for explicit negation around outcome words. Subtle disagreements can be missed, and the topic label is a list of shared stems.
- The agent does not decide which conflicting source is right.
- Scanned pages are flagged. They are not OCR'd.
- Remote prose is not shown. Only verified claims are.
- The published evaluation scores are for ten synthetic questions. See `docs/EVALUATION.md`.
