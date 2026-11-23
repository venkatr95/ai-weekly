# PRD: Personal Document Change Detector

## 1. Product vision

Build an intelligent document comparison tool that detects, categorizes, and explains changes between different versions of personal and professional documents.

Users provide two versions of a document. The application compares the content and generates a structured report explaining:

- What was added.
- What was removed.
- What was modified.
- Which sections changed.
- Which changes may be important.
- What the practical implications might be.
- Which changes require human review.

The tool should support contracts, policies, reports, proposals, financial documents, and general PDFs.

## 2. Unique value proposition (UVP)

Traditional document comparison tools show textual differences.

This project explains the significance of those differences.

**The Personal Document Change Detector transforms raw document differences into understandable, prioritized change intelligence.**

Key differentiators:

- Detects meaningful changes rather than just formatting differences.
- Explains changes in plain language.
- Highlights potentially important clauses and obligations.
- Identifies modified dates, amounts, names, and responsibilities.
- Preserves references to original document pages and sections.
- Separates actual textual changes from AI-generated interpretations.
- Works locally with user-provided documents.

## 3. Target users

- Individuals managing contracts and agreements.
- Researchers comparing paper revisions.
- Business professionals reviewing proposals.
- Employees reviewing updated company policies.
- Project managers comparing project documentation.
- Consultants reviewing client deliverables.
- Developers building document intelligence applications.

## 4. Goals and non-goals

### Goals

1. Accept two document versions.
2. Support PDF, DOCX, TXT, and Markdown.
3. Extract and normalize document text.
4. Identify additions, removals, and modifications.
5. Align corresponding sections between versions.
6. Detect important numerical and contractual changes.
7. Explain meaningful changes using an LLM.
8. Classify changes by category and importance.
9. Provide source references and page numbers where available.
10. Generate Markdown and JSON reports.
11. Provide a CLI and reusable Python API.
12. Include automated tests and comprehensive documentation.

### Non-goals for version 1

- Automatically editing documents.
- Signing or approving contracts.
- Providing legal advice.
- Predicting the outcome of disputes.
- Automatically accepting or rejecting proposed changes.
- Monitoring cloud storage continuously.
- Replacing professional document review.

## 5. Core user experience

### Example input

**Document A: Previous employment agreement**

- Annual salary: €60,000.
- Notice period: 30 days.
- Remote work: Three days per week.
- Annual leave: 25 days.

**Document B: Updated employment agreement**

- Annual salary: €65,000.
- Notice period: 90 days.
- Remote work: One day per week.
- Annual leave: 25 days.

### Expected output

**Document comparison summary**

4 changes detected

| Section | Previous version | New version | Assessment |
|---|---|---|---|
| Salary | €60,000 | €65,000 | Increased |
| Notice period | 30 days | 90 days | Significant change |
| Remote work | 3 days/week | 1 day/week | Significant change |
| Annual leave | 25 days | 25 days | Unchanged |

**Detailed change analysis**

1. Salary increased by €5,000 annually (approximately 8.33%).
2. Notice period increased from 30 to 90 days. This may materially affect the timing of termination.
3. Remote working entitlement decreased from three days to one day per week.
4. Annual leave entitlement remains unchanged.

**Recommended review priorities**

- Review the new notice period.
- Confirm that the remote-working arrangement is acceptable.
- Verify whether other sections introduce additional obligations.

**Important:** The tool identifies differences and explains potential implications. It does not determine whether a contractual change is legally valid or enforceable.

## 6. Functional requirements

### FR-1: Document ingestion

Support PDF, DOCX, TXT, and Markdown. Accept two individual files. Preserve filenames, PDF page numbers, and headings where possible. Handle empty, encrypted, corrupt, and unreadable files with explicit errors. For scanned PDFs, detect when OCR is needed.

### FR-2: Document normalization

Normalize whitespace and line endings. Detect repeated headers and footers where practical. Preserve headings, tables, numerical content, currency symbols, percentages, dates, and negative values. Retain original text for evidence verification.

### FR-3: Structural comparison

Match headings, renamed headings, reordered sections, added/removed sections, modified paragraphs, and modified table rows using section-aware matching.

### FR-4: Textual difference detection

Detect additions, removals, replacements, moved sections, formatting-only changes, and changes to numbers, dates, names, and responsibilities. Use deterministic text-diff first. LLMs explain changes; they are not the sole mechanism for deciding whether text changed.

### FR-5: Semantic change detection

Flag wording changes that alter meaning (for example remote-work days or obligation strength: "shall" vs "should aim to").

### FR-6: Change categorization

Classify into: financial, legal or contractual wording, dates and deadlines, responsibilities, access and permissions, policy changes, operational requirements, numerical changes, personnel or organizational changes, general textual changes. Multiple categories allowed.

### FR-7: Importance classification

Critical, High, Medium, Low, Informational — each with an explanation. Importance is a review-priority indicator, not a legal or financial risk determination.

### FR-8: Numerical and date comparison

Detect prices, salaries, percentages, quantities, interest rates, deadlines, durations, payment terms, notice periods, and dates. Preserve units and currencies. Calculate absolute and percentage difference when valid.

### FR-9: AI-generated explanations

For each meaningful change: title, previous/new wording, plain-language explanation, potential implication, importance, review recommendation, and source references. Do not invent implications beyond available text.

### FR-10: Change evidence and traceability

Every change references document identifiers, pages, sections, and exact previous/updated text. AI explanations stay separate from quotations. Quotations must appear in extracted source text.

### FR-11–FR-14

Structured Pydantic JSON output, Markdown/JSON reports, CLI (`compare`), and security/privacy safeguards (untrusted document content, env-based API keys, no automatic uploads).

## 7–13. Architecture, stack, workflow, evaluation, acceptance, milestones

See [ARCHITECTURE.md](ARCHITECTURE.md), [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), and [docs/](docs/) for the recommended layout, technology stack, processing workflow, evaluation strategy, acceptance criteria, milestones, and definition of done.
