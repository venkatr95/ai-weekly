# Architecture

## Pipeline

1. **Load** previous and updated files (`document_loader`, PDF/DOCX/text extractors).
2. **Normalize** whitespace and repeated headers/footers (`text_normalizer`) while keeping currencies, dates, and signs.
3. **Parse sections** from headings (`section_parser`).
4. **Align sections** by title and body similarity (`document_aligner`).
5. **Diff** paragraphs with `difflib` (`text_diff`). Formatting-only changes are flagged separately.
6. **Detect numbers/dates/obligations** (`impact_analyzer`).
7. **Classify** categories and importance (`change_classifier`).
8. **Explain** with the heuristic provider or xAI (`providers`). The model never decides whether text changed.
9. **Validate quotations** against original extracted text (`evidence_validator`).
10. **Render** Markdown or JSON (`report_generator`).

## Design rules

- Deterministic comparison is authoritative for *what* changed.
- LLM / heuristic text is labeled as interpretation.
- Document contents are untrusted input; prompts fence them and forbid instruction-following.
- API keys stay in the environment and are scrubbed from error messages.
- Only changed excerpts are sent to an LLM, not entire documents when avoidable.
