# PRD: AI Answer Auditor

## 1. Product vision

Build an auditing tool that evaluates whether an AI-generated answer is supported by its source documents.

Users provide:

1. An AI-generated answer.
2. One or more source documents.
3. Optionally, the original question.

The system segments the answer into atomic claims, checks each claim against the source material, and produces an evidence-backed verification report.

The auditor distinguishes supported, partially supported, unsupported, contradicted, and unverifiable claims.

## 2. Unique value proposition

Most AI systems focus on generating answers. This project checks whether those answers are supported by the documents the user supplied.

The auditor is an evidence layer between an AI-generated answer and the reader.

- Verification is claim by claim, not a single accuracy score.
- Every positive or negative decision that depends on a passage includes the passage.
- Claims that go beyond the sources are marked partially supported or unsupported.
- Contradictions are explicit.
- JSON output can be consumed by another workflow.
- Missing evidence and contradictory evidence are different statuses.

## 3. Target users

- Developers building RAG applications.
- AI engineers evaluating model answers.
- Researchers checking AI-assisted summaries.
- Content teams validating generated reports.
- Analysts reviewing AI-generated business notes.
- Teams building quality checks around model output.

## 4. Goals and non-goals

### Goals

1. Accept an AI-generated answer.
2. Accept multiple source documents.
3. Split the answer into atomic factual claims.
4. Verify each claim against the provided sources.
5. Identify supporting and contradicting passages.
6. Assign a verification status to every claim.
7. Provide a short explanation for every decision.
8. Calculate an evidence coverage score.
9. Generate Markdown and JSON reports.
10. Provide a CLI and a Python API.
11. Include automated tests and documentation.

### Non-goals for version 1

- Searching the public internet.
- Rewriting the original answer.
- Guaranteeing truth beyond the supplied sources.
- Replacing professional legal, scientific, or editorial review.
- Training or fine-tuning a model.
- Autonomous agent behavior.
- Treating a model's confidence as proof.

## 5. Sample

Question: What were the results of the company's 2025 financial performance?

Answer: The company generated €120 million in revenue in 2025. Revenue increased by 25% compared with 2024. The company also achieved a net profit of €18 million and expanded its workforce by 15%.

Sources:

- Annual report: revenue for 2025 was €120 million, compared with €100 million in 2024.
- Financial statement: net profit was €15 million.
- Workforce report: 460 people at the end of 2025, compared with 400 in 2024.

The requirements sketch labeled the 25% sentence as supported. The figures are a 20% increase, so this implementation marks that claim contradicted. The workforce sentence is partially supported because 15% is implied and not stated. See [docs/EVALUATION.md](docs/EVALUATION.md).

## 6. Functional requirements

### FR-1 Input

Accept an answer, an optional question, and multiple sources with ids and titles. Formats: `.txt`, `.md`, `.pdf`, and JSON. The demo uses three sources.

### FR-2 Claim extraction

Identify atomic factual statements. Split compound sentences. Preserve wording, assign a stable id, and keep sentence and paragraph indexes. Label opinions, recommendations, and non-factual lines. Do not invent claims.

### FR-3 Evidence retrieval

Search the supplied documents, keep source ids and page numbers, and return enough of the sentence to interpret it. Also surface passages that may conflict. Absence of a retrieved passage does not mean the claim is false.

### FR-4 Verification

Supported means the source states the claim. Partially supported means the source establishes part of it, including a calculated percentage that the source does not state. Contradicted means a passage conflicts with the claim. Unsupported means the sources are insufficient. Unverifiable means the line cannot be checked from the documents.

Each decision includes the claim id, the claim text, the status, an explanation, supporting evidence, contradicting evidence, source references, and notes.

### FR-5 Evidence quality

Do not invent quotations. Check that each quote occurs in the extracted text. Keep quotes separate from explanations. Do not treat missing evidence as contradiction. Allow several sources to bear on one claim, and keep conflicting passages.

### FR-6 Summary

Report total, supported, partially supported, contradicted, unsupported, and unverifiable counts, plus evidence coverage and an overall assessment. Coverage is supported claims divided by factual claims. Partial support is not counted as fully supported.

### FR-7 Structured output

JSON validated by Pydantic before it is returned. The shape is documented in [docs/API.md](docs/API.md).

### FR-8 Reports

Markdown includes the executive summary, statistics, claim-by-claim results, quotations, and review actions. JSON includes stable ids, source metadata, and the status values.

### FR-9 CLI

`audit`, `extract-claims`, and `evaluate`, as shown in [docs/USAGE.md](docs/USAGE.md). Files and directories are both accepted.

### FR-10 Security

Documents are untrusted. Embedded instructions are ignored. File contents are not executed. Credentials stay in the environment. Source text is not logged by default. Parse failures are reported. Secrets are redacted in reports. Provider data handling is documented in [docs/SECURITY.md](docs/SECURITY.md).

## 7. Stack

Python 3.11+, Pydantic, PyMuPDF, a small sentence segmenter, an optional xAI provider behind the same interface, and pytest. The heuristic checker is the default so the core path does not depend on a particular model.

## 8. Acceptance

The implementation accepts an answer and three sources, reads PDF, text, and Markdown, extracts and splits claims, assigns all five statuses, quotes sources for support and contradiction, checks those quotes, detects conflicts, writes Markdown and JSON, exposes a CLI and a Python API, and passes the unit and integration tests. The reproducible demo is `examples/answer.txt` with `examples/sources/`.
