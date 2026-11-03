# AI Answer Auditor

The AI Answer Auditor checks whether an AI-generated answer is supported by the source documents you supply. It splits the answer into claims, compares each claim with the sources, and writes an evidence-backed report.

A supported claim quotes a passage that states it. A contradicted claim quotes a passage that conflicts with it. A claim with no relevant passage is unsupported. Missing evidence is not treated as proof that the claim is false.

The default checker is deterministic. It does not call a model, and it does not treat a model's confidence as evidence. An optional xAI provider can propose claims and statuses. Every quotation is still checked against the extracted source text, and a numeric contradiction found by the deterministic checker is kept.

## Demo

The bundled answer says revenue rose 25% and net profit was €18 million. The sources say revenue went from €100 million to €120 million, which is a 20% increase, and that net profit was €15 million.

```bash
python cli.py audit --answer examples/answer.txt --sources examples/sources --question "What were the results of the company's 2025 financial performance?"
```

| Claim | Status | Why |
| --- | --- | --- |
| Revenue was €120 million in 2025 | Supported | The annual report states €120 million for 2025. |
| Revenue increased by 25% | Contradicted | €120 million against €100 million is a 20% increase. |
| Net profit was €18 million | Contradicted | The financial statement says €15 million. |
| Workforce expanded by 15% | Partially supported | 460 employees against 400 is a 15% increase, and the source does not state the percentage. |

Evidence coverage is 25%. Coverage counts fully supported claims only. Partial support is reported on its own. The saved JSON for this run is [examples/expected_report.json](examples/expected_report.json).

## Install

Python 3.11 or newer. On this machine use the `py` launcher if `python` is not on `PATH`.

```bash
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

macOS and Linux use `source .venv/bin/activate`.

## Use

```bash
python cli.py audit --answer answer.txt --sources source1.pdf source2.pdf source3.pdf
python cli.py audit --answer answer.txt --sources ./sources/ --question "What happened in 2025?"
python cli.py audit --answer answer.txt --sources ./sources/ --format json
python cli.py extract-claims --answer answer.txt
python cli.py evaluate
streamlit run streamlit_app.py
pytest -q
```

`--sources` accepts files and directories. Supported source types are `.txt`, `.md`, `.pdf`, and `.json`. A directory skips unsupported files and records a warning. A file you name directly must be a supported type.

From Python:

```python
from answer_auditor import audit

report = audit(
    "Revenue was €120 million in 2025.",
    [{"source_id": "S1", "title": "Annual report", "text": "Revenue for 2025 amounted to €120 million."}],
    question="What was 2025 revenue?",
)
print(report.summary.evidence_coverage)
```

## Web UI

```bash
streamlit run streamlit_app.py
```

The page starts with the bundled answer and the three sources. Paste another answer, edit the source boxes, or upload `.txt`, `.md`, `.pdf`, or `.json` files. An uploaded file is audited instead of the text boxes. Load example restores the demo and clears the upload.

The provider starts on `heuristic`, including when `AUDITOR_PROVIDER` is `xai`. Choose `xai` only when the answer and the passages can be sent to xAI. The page does not show the API key.

The Claims tab is the checklist. The Report tab downloads the validated Markdown and JSON from the same renderer as the CLI.

## Documentation

- [Installation](docs/INSTALLATION.md)
- [Configuration](docs/CONFIGURATION.md)
- [Usage](docs/USAGE.md)
- [Architecture](ARCHITECTURE.md)
- [Python API](docs/API.md)
- [Evaluation](docs/EVALUATION.md)
- [Security](docs/SECURITY.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Product requirements](PRD.md)
