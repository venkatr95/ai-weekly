# Architecture

The design reference is [../ARCHITECTURE.md](../ARCHITECTURE.md). This page is the short operational view.

## Data flow

```text
old file + new file
    -> document loader / PDF · DOCX · text extractors
    -> text normalizer
    -> section parser
    -> document aligner
    -> text diff
    -> impact analyzer / change classifier
    -> heuristic or xAI explanations
    -> evidence validator
    -> Pydantic ComparisonReport
    -> Markdown or JSON
```

Deterministic comparison decides *what* changed. The provider only explains and prioritizes. The validator then checks that every quotation is a real span of the extracted text.

`streamlit_app.py` is another entry point. It calls `compare()` and does not invent its own change list.

## Modules

| Stage | Module |
| --- | --- |
| Load PDF, DOCX, TXT, Markdown | `document_loader.py`, `pdf_extractor.py`, `docx_extractor.py` |
| Normalize whitespace; keep currencies and dates | `text_normalizer.py` |
| Detect headings and sections | `section_parser.py` |
| Align corresponding sections | `document_aligner.py` |
| Diff paragraphs (`difflib`) | `text_diff.py` |
| Numerical, date, and obligation signals | `impact_analyzer.py` |
| Categories and importance | `change_classifier.py` |
| Heuristic or xAI explanations | `providers.py` |
| Quotation checks | `evidence_validator.py` |
| Summary, recommendations, render | `report_generator.py` |
| Orchestration | `pipeline.py` |
| Report schema | `schemas.py` |
| Untrusted-input fencing and redaction | `security.py` |
| Browser page | `streamlit_app.py` calls `compare()` |

## Provider boundary

The heuristic provider is the default and does not use the network. The xAI provider may refine explanation text, but diffs and evidence validation still run. See [SECURITY.md](SECURITY.md) for how change excerpts are sent.
