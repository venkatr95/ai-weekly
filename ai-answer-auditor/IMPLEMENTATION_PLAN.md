# Implementation plan

Version 1 is implemented in this repository. The milestones below are the build order, and each one names the modules that carry it.

## Milestone 1: Input and extraction

- Package layout under `src/answer_auditor/`, with `cli.py` at the project root.
- `document_loader.py` and `text_extractor.py` read `.txt`, `.md`, `.pdf`, and JSON. Directories are supported. PDF pages keep their numbers. Encrypted and unreadable PDFs raise a clear parse error. Scanned pages are flagged and are not OCR'd.
- `sentence_segmenter.py` splits sentences and paragraphs, including abbreviations and decimals.
- Tests: `test_document_loader.py`, `test_sentence_segmentation.py`.

## Milestone 2: Claim extraction

- `claim_extractor.py` splits coordinated clauses, keeps the subject on a bare verb phrase, and assigns `C001` style ids.
- Opinions, recommendations, and non-factual lines are labeled and are not turned into invented facts.
- `schemas.py` defines the claim and report models.
- Tests: `test_claim_extraction.py`.

## Milestone 3: Evidence and verification

- `evidence_retriever.py` selects sentences by metric overlap and wording. A miss is not a verdict.
- `claim_verifier.py` assigns supported, partially supported, contradicted, unsupported, and unverifiable.
- Comparisons, explicit percentages, implied percentages, negation, and conflicting sources are handled in that module.
- Tests: `test_evidence_retrieval.py`, `test_claim_verification.py`.

## Milestone 4: Validation and reporting

- `evidence_validator.py` drops quotations that are not in the extracted text and downgrades a status that no longer has its evidence.
- `report_generator.py` writes Markdown and JSON. Coverage is supported claims divided by factual claims. Partial support is not counted as supported.
- `AuditReport` rejects inconsistent counts.
- Tests: `test_evidence_validation.py`, `test_report_generation.py`.

## Milestone 5: Reliability and documentation

- `security.py` treats document text as untrusted data and redacts secrets in the report.
- `providers.py` adds the optional xAI provider. The deterministic checker overrules a model when the figures conflict, and `store` is false on the request.
- `examples/benchmark.json` and `evaluation.py` score manually labeled cases. The labels are the judge.
- `examples/answer.txt` and `examples/sources/` are the three-source demonstration. `examples/expected_report.json` is the report that command produces.
- Documentation is in `README.md`, `ARCHITECTURE.md`, and `docs/`.
- Tests: `test_end_to_end.py`, plus `pytest -q` and `python cli.py evaluate`.

## Done when

A developer installs the dependencies, passes the sample answer and the three sources to `python cli.py audit`, and receives a claim-by-claim report. Each status points at a quotation or at an explicit lack of evidence.
