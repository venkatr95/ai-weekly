# Python API

```python
from answer_auditor import audit, extract_claims, AuditReport
```

## audit

```python
audit(
    answer: str,
    sources: list[str | Path | dict],
    question: str | None = None,
    settings: Settings | None = None,
) -> AuditReport
```

`sources` may contain file paths, directory paths, and dictionaries. A dictionary uses `text` or `path`, and may set `source_id` and `title`.

An empty answer, a missing file, an unsupported file you named directly, or a directory with no readable sources raises `InputError` or `ParseError`. Both inherit from `AuditorError`.

## extract_claims

```python
extract_claims(answer: str, settings: Settings | None = None) -> list[ExtractedClaim]
```

Returns claims with stable ids. It does not load sources.

## AuditReport

| Field | Meaning |
| --- | --- |
| `question` | The optional question, or null. |
| `overall_assessment` | One sentence naming the statuses that appear. |
| `summary` | Counts and `evidence_coverage`. |
| `claims` | One result per claim. |
| `sources` | Id, title, path, file type, and page count when the file has pages. |
| `warnings` | Skipped files, scanned pages, and dropped model claims. |
| `provider` | `heuristic` or `xai`. |

### summary

| Field | Meaning |
| --- | --- |
| `total_claims` | Every extracted claim, including opinions. |
| `supported` | Fully supported factual claims. |
| `partially_supported` | Not included in `supported`. |
| `contradicted` | Claims that conflict with a passage. |
| `unsupported` | Claims the sources do not establish. |
| `unverifiable` | Claims that cannot be checked from documents. |
| `factual_claims` | Claims whose type is `factual`. |
| `evidence_coverage` | `100 * supported / factual_claims`, rounded to one decimal. Null when there are no factual claims. |

### claims

| Field | Meaning |
| --- | --- |
| `claim_id` | `C001`, `C002`, in reading order. |
| `text` | The claim wording. |
| `claim_type` | `factual`, `opinion`, `recommendation`, or `non_factual`. |
| `status` | `supported`, `partially_supported`, `contradicted`, `unsupported`, or `unverifiable`. |
| `explanation` | Why the status was assigned. This is separate from the quotations. |
| `supporting_evidence` | Passages that support the claim. |
| `contradicting_evidence` | Passages that conflict with the claim. |
| `verification_notes` | Extra limits, such as an implied percentage or a conflict between sources. |
| `sentence_index` | Sentence number in the answer, starting at 1. |
| `paragraph_index` | Paragraph number, starting at 1. |
| `original_sentence` | The answer sentence the claim came from. |

### Evidence objects

| Field | Meaning |
| --- | --- |
| `source_id` | Id of the source document. |
| `quote` | A span of the extracted source text. |
| `page` | PDF page number, or null. |
| `source_title` | Title from the file, when one was found. |

The schema rejects a report whose counts do not add up, or whose coverage does not equal supported claims divided by factual claims.

## Settings

```python
from answer_auditor.config import Settings, load_settings

settings = load_settings()  # reads the environment and a local .env
settings = Settings(provider="heuristic")
```

`load_settings("xai")` raises `ConfigurationError` when `XAI_API_KEY` is missing.

## Errors

| Exception | When |
| --- | --- |
| `InputError` | Empty answer, missing JSON request, or no usable sources. |
| `ParseError` | Unreadable file, bad encoding, encrypted PDF, or unsupported type. |
| `ConfigurationError` | Unknown provider, or `xai` without an API key. |
| `ProviderError` | The model request failed or returned JSON that could not be used. |
