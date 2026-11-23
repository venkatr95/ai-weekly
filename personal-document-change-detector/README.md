# Personal Document Change Detector

Compare two versions of a personal or professional document and get a prioritized report of what changed, where it changed, and why it may matter.

Deterministic text comparison finds additions, removals, and modifications. Heuristic (or optional xAI) explanations classify importance and describe practical implications. Quotations are validated against the extracted source text. The tool does **not** provide legal advice.

## Quick start

```bash
cd personal-document-change-detector
py -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

python cli.py compare --old examples/documents/employment_v1.md --new examples/documents/employment_v2.md
python cli.py compare --old examples/documents/employment_v1.md --new examples/documents/employment_v2.md --format json
python cli.py compare --old examples/documents/employment_v1.md --new examples/documents/employment_v2.md --min-importance high

pytest -q
streamlit run streamlit_app.py
```

Optional LLM explanations:

```bash
# .env
DETECTOR_PROVIDER=xai
XAI_API_KEY=your_key
XAI_MODEL=grok-4.7
```

## Supported formats

PDF, DOCX, TXT, Markdown.

## Python API

```python
from document_detector import compare

report = compare("old.pdf", "new.pdf")
for change in report.changes:
    print(change.change_id, change.importance, change.title)
```

## Layout

- `cli.py` — command-line entry point
- `streamlit_app.py` — browser UI over the same pipeline
- `src/document_detector/` — extraction, alignment, diff, classification, reporting
- `examples/documents/` — sample document pairs
- `docs/` — installation, usage, architecture, security, and evaluation notes

See [PRD.md](PRD.md) for product requirements.
