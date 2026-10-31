# Architecture

The auditor checks an answer against documents you supply. It does not search the web, rewrite the answer, or decide that a claim is true outside those documents.

## Workflow

1. Load the answer and one or more sources.
2. Extract text. PDF page numbers are preserved. A scanned page with no text layer is flagged and is not OCR'd.
3. Segment the answer into sentences and paragraphs.
4. Split coordinated clauses into atomic claims and label opinions, recommendations, and non-factual lines.
5. Retrieve source sentences that share a metric or enough wording with each claim.
6. Compare the claim with those sentences and assign a status.
7. Drop any quotation that is not a span of the extracted source text.
8. Validate the report with Pydantic, then render Markdown or JSON.

Source text is data. Nothing in a document is executed, and instructions inside a document are not treated as commands.

## Statuses

| Status | Meaning |
| --- | --- |
| `supported` | A source passage explicitly establishes the claim. |
| `partially_supported` | The sources establish part of the claim, or a percentage follows from two figures but is not stated. |
| `contradicted` | A source passage conflicts with the claim. |
| `unsupported` | The sources do not contain enough evidence. This is not a finding that the claim is false. |
| `unverifiable` | The statement is an opinion, a recommendation, or otherwise not checkable from documents. |

Evidence coverage is the number of supported claims divided by the number of factual claims, as a percentage rounded to one decimal place. Partially supported claims stay in their own count. Opinions, recommendations, and non-factual lines are not factual claims, so they are outside the coverage denominator.

When two sources disagree, the report keeps both passages. The status is partially supported, with a note that the sources conflict. A claim that matches neither source is contradicted.

## Modules

| Module | Responsibility |
| --- | --- |
| `document_loader.py` | Read files, directories, and JSON requests. Assign source ids. |
| `text_extractor.py` | Decode text and extract PDF pages with PyMuPDF. |
| `sentence_segmenter.py` | Split sentences without breaking abbreviations or decimals. |
| `claim_extractor.py` | Build atomic claims from the answer only. |
| `evidence_retriever.py` | Select relevant source sentences. Retrieval is not a verdict. |
| `claim_verifier.py` | Compare figures, percentages, negation, and wording. |
| `evidence_validator.py` | Reject quotations that are not in the source text. |
| `report_generator.py` | Build the summary, Markdown, and JSON. |
| `providers.py` | Heuristic provider, and the optional xAI provider. |
| `pipeline.py` | Run the workflow and validate the report. |
| `evaluation.py` | Score labeled examples. The labels are the judge. |
| `security.py` | Prompts that treat documents as untrusted data, and secret redaction. |
| `schemas.py` | Pydantic models. Invalid counts and coverage cannot be returned. |

## Providers

`heuristic` is the default. It runs offline. The same rules produce the same report.

`xai` sends the claim and the retrieved passages to `POST https://api.x.ai/v1/responses` using `XAI_API_KEY`. The default model is `grok-4.7`. The request sets `store` to false so the provider is asked not to retain the conversation. Passages are wrapped as untrusted data, separate from the instructions.

The model cannot finish the audit on its own:

- A quotation that is not in the source is dropped. A supported or contradicted status with no remaining quotation is downgraded to unsupported.
- If the deterministic checker finds a numeric contradiction, that status replaces a model status of supported or partially supported.
- A percentage that is only calculated from two figures stays partially supported, even if the model calls it supported.
- A model contradiction with no conflicting passage stays unsupported.
- A proposed claim whose wording is not in the answer is dropped.

## What the checker covers

The deterministic checker compares currency amounts, counts, years, and percentages. It reads comparisons written with "compared with" or "from … to …". It treats "hired" separately from headcount, so a hiring claim is not judged against a workforce total. Negated sentences are not used as support for the positive claim.

A percentage stated in the source can be supported. A percentage that only follows from two figures is partially supported when the arithmetic matches, and contradicted when it does not. The baseline must be positive. A zero or negative baseline is not turned into a percentage.

Qualitative claims need substantial wording overlap with a source sentence. The checker is not a general reading-comprehension system. Claims about scope that the source never mentions, such as a region, are partially supported when the rest of the figure matches.

## Limits

The report is only as complete as the extracted text. Scanned PDFs, encrypted PDFs, and files that are not UTF-8 are reported as failures rather than silently skipped when you name them directly. The checker does not infer facts that the sources do not state, and it does not correct the original answer.
