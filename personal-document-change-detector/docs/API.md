# Python API

```python
from document_detector import compare, ComparisonReport
```

## compare

```python
compare(
    old_path: str | Path,
    new_path: str | Path,
    *,
    settings: Settings | None = None,
    min_importance: str = "informational",
    include_formatting: bool = False,
    comparison_id: str = "comparison_001",
) -> ComparisonReport
```

`old_path` and `new_path` are file paths. Supported suffixes are `.pdf`, `.docx`, `.txt`, `.md`, and `.markdown`.

A missing file, an empty extract, an unsupported type, or an encrypted PDF raises `InputError` or `ParseError`. Both inherit from `DetectorError`.

`min_importance` drops changes below that level after classification. `include_formatting` keeps formatting-only differences when true.

## ComparisonReport

| Field | Meaning |
| --- | --- |
| `comparison_id` | Id for this run. |
| `documents` | Map with `previous` and `updated` `DocumentInfo` entries. |
| `summary` | Counts by change type and importance. |
| `changes` | One `ChangeRecord` per retained difference. |
| `review_recommendations` | Short review prompts for higher-priority changes. |
| `warnings` | Empty files, scanned pages, and dropped quotations. |
| `provider` | `heuristic` or `xai`. |
| `disclaimer` | Not legal, financial, or professional advice. |

### documents / DocumentInfo

| Field | Meaning |
| --- | --- |
| `document_id` | `previous` or `updated`. |
| `filename` | Basename of the file. |
| `path` | Path string when known. |
| `file_type` | `pdf`, `docx`, `txt`, or `md`. |
| `page_count` | PDF page count, or null. |

### summary

| Field | Meaning |
| --- | --- |
| `total_changes` | Length of `changes`. |
| `added` / `removed` / `modified` / `moved` | Counts by change type. |
| `formatting_only` | Subset that is formatting-only. |
| `critical` / `high` / `medium` / `low` / `informational` | Counts by importance. |

The schema rejects a report whose type or importance counts do not match `total_changes`.

### ChangeRecord

| Field | Meaning |
| --- | --- |
| `change_id` | `CH001`, `CH002`, in detection order. |
| `change_type` | `added`, `removed`, `modified`, `moved`, `unchanged`, or `formatting`. |
| `categories` | One or more of financial, legal_contractual, dates_deadlines, responsibilities, access_permissions, policy, operational, numerical, personnel, general. |
| `importance` | `critical`, `high`, `medium`, `low`, or `informational`. |
| `importance_reason` | Why that priority was chosen. |
| `section` | Aligned section title when known. |
| `title` | Short label for the change. |
| `previous_text` / `updated_text` | Quoted wording from each version. |
| `explanation` | Heuristic or model interpretation. Separate from the quotations. |
| `impact` | Possible practical implication for human review. |
| `recommendation` | Suggested review action. |
| `previous_page` / `updated_page` | PDF page numbers, or null. |
| `previous_document_id` / `updated_document_id` | Usually `previous` and `updated`. |
| `numerical` | Optional `NumericalDelta` for amounts, durations, and similar. |
| `formatting_only` | True when only presentation changed. |
| `evidence_validated` | True when the quotations appear in the extracted text. |

### NumericalDelta

| Field | Meaning |
| --- | --- |
| `kind` | For example `currency` or `value`. |
| `previous_value` / `updated_value` | Parsed numbers when available. |
| `unit` / `currency` | Preserved units when detected. |
| `absolute_difference` / `percentage_difference` | Calculated when both values exist. |
| `direction` | `increased`, `decreased`, `unchanged`, or `unknown`. |

## Settings

```python
from document_detector.config import Settings, load_settings

settings = load_settings()  # reads the environment and a local .env
settings = Settings(provider="heuristic")
```

`load_settings("xai")` raises `ConfigurationError` when `XAI_API_KEY` is missing.

## Browser page

`streamlit_app.py` calls `compare()` with the uploaded or example paths, the provider selected on the page, minimum importance, and the formatting switch. Uploads are written to temporary files only long enough to parse them. The page starts on the heuristic provider.

## Errors

| Exception | When |
| --- | --- |
| `InputError` | Missing path, unsupported type, or no extractable text. |
| `ParseError` | Unreadable file, bad encoding, encrypted PDF, or missing PyMuPDF. |
| `ConfigurationError` | Unknown provider, or `xai` without an API key. |
| `ProviderError` | The model request failed or returned JSON that could not be used. |
