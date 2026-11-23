# Usage

## Compare files

```bash
python cli.py compare --old previous.pdf --new updated.pdf
python cli.py compare --old examples/documents/employment_v1.md --new examples/documents/employment_v2.md
python cli.py compare --old examples/documents/employment_v1.md --new examples/documents/employment_v2.md --format json
python cli.py compare --old examples/documents/employment_v1.md --new examples/documents/employment_v2.md --min-importance high
python cli.py compare --old old.docx --new new.docx --include-formatting --output report.md
```

`--old` and `--new` are required. Supported types are `.pdf`, `.docx`, `.txt`, `.md`, and `.markdown`.

`--format` is `markdown` or `json`. Markdown is the default. `--output` also writes the report to a file. Without `--output`, the process prints the report.

`--min-importance` hides changes below that level. Values are `critical`, `high`, `medium`, `low`, and `informational` (the default). `--include-formatting` keeps formatting-only differences; they are omitted otherwise.

`--provider heuristic` or `--provider xai` overrides `DETECTOR_PROVIDER` for that run. `--comparison-id` sets the report id (default `comparison_001`).

Exit code `0` means a report was written. Exit code `2` means an input, parse, configuration, or provider failure.

## Web UI

```bash
streamlit run streamlit_app.py
```

The page calls `compare()` with the same provider, minimum importance, and formatting switch as the CLI. Upload a previous and an updated file, or load an example pair from `examples/documents/`. When uploads are present, those files are the input.

The provider menu starts on `heuristic`. `xai` uses `XAI_API_KEY` from the environment or `.env` and sends change excerpts to xAI. The Markdown and JSON downloads are `render_markdown` and `render_json`.

## Python

```python
from document_detector import compare

report = compare(
    "examples/documents/employment_v1.md",
    "examples/documents/employment_v2.md",
    min_importance="informational",
    include_formatting=False,
)
for change in report.changes:
    print(change.change_id, change.importance, change.title)
```

`report.model_dump(mode="json")` is the JSON document. Field definitions are in [API.md](API.md). Illustrative employment output is in `examples/expected_report.md` and `examples/expected_report.json`.

## How to read a change

- Added / removed / modified / moved: deterministic text comparison decided that the wording differs.
- Formatting only: whitespace or presentation changed; substance did not. Hidden unless `--include-formatting` is set.
- Importance (`critical` … `informational`): a review-priority label, not a legal or financial risk score.
- Explanation and impact: heuristic or model interpretation. They are separate from the quoted previous and updated wording.
- Evidence validated: the quoted spans appear in the extracted document text.

The report disclaimer states that the tool does not provide legal advice and does not decide whether a change is valid or enforceable.
