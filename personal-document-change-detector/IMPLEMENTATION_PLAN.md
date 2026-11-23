# Implementation plan

## Milestone 1 — Document extraction

- [x] Project structure and packaging under `src/document_detector`
- [x] PDF extraction with page numbers (PyMuPDF)
- [x] DOCX extraction (python-docx)
- [x] TXT and Markdown support
- [x] Explicit errors for empty, encrypted, and unsupported files

## Milestone 2 — Text comparison

- [x] Normalization that preserves meaningful symbols
- [x] Section detection and alignment
- [x] Additions, removals, modifications via difflib
- [x] Deterministic unit tests

## Milestone 3 — Semantic change analysis

- [x] Numerical and date deltas
- [x] Obligation-strength heuristics
- [x] Category and importance classification
- [x] Optional xAI explanations with heuristic fallback fields

## Milestone 4 — Reporting

- [x] Pydantic schemas and summary validation
- [x] JSON and Markdown reports
- [x] Evidence validation
- [x] Review recommendations and disclaimer

## Milestone 5 — Reliability and documentation

- [x] Example document pairs
- [x] Automated tests including end-to-end and web UI helpers
- [x] Security notes and docs
- [x] CLI and Streamlit entry points
