# Evaluation

Judge the detector on labeled document pairs. The employment and supplier samples under `examples/documents/` are the starting set. A person marks which textual changes must be found; the report is scored against those labels.

The labels are the judge. Heuristic (or model) explanations, importance reasons, and impact wording are **not** ground truth. Score detection and quotation fidelity first. Treat explanation text as optional commentary.

## What to measure

| Check | What it tells you |
| --- | --- |
| Change recall | Share of labeled differences that appear in `changes` with matching previous/updated wording (or an equivalent span). |
| Change precision | Share of reported non-formatting changes that match a labeled difference. |
| Quotation validity | Share of `previous_text` / `updated_text` spans that occur in the extracted document text (`evidence_validated`). |
| Numerical fidelity | For labeled amount or duration changes, whether direction and approximate magnitude match. |
| Importance ranking (optional) | Whether high-priority labeled items land in `critical` or `high` when `--min-importance high` is used. |

A pair passes detection when every labeled change is recalled and every reported substantive change is precise. Explanation wording can differ without failing the pair.

## Employment sample

`employment_v1.md` → `employment_v2.md` should surface at least:

| Section | Previous | Updated |
| --- | --- | --- |
| Compensation | €60,000 | €65,000 |
| Notice Period | 30 days | 90 days |
| Remote Work | three days per week | one day per week |

Annual leave (25 days) stays unchanged and should not appear as a change. Illustrative reports are `examples/expected_report.md` and `examples/expected_report.json`.

When scoring that pair:

- Salary and notice period should carry a numerical delta.
- Notice period and remote work should rank at least `high` under the default heuristic.
- Do not fail the pair because the explanation says "8.33%" instead of "approximately 8%" — that text is interpretation.

## How to run a manual check

```bash
python cli.py compare --old examples/documents/employment_v1.md --new examples/documents/employment_v2.md --format json
python cli.py compare --old examples/documents/employment_v1.md --new examples/documents/employment_v2.md --min-importance high
pytest -q
```

`pytest -q` covers loading, normalization, alignment, diffs, numerical deltas, classification, evidence validation, end-to-end employment comparison, and the Streamlit helpers. It does not treat free-form explanation strings as golden text.

## What this does not measure

- Legal correctness, enforceability, or negotiation outcome.
- OCR quality on scanned PDFs (pages without a text layer are not transcribed).
- Live xAI quality. The xAI path is covered with a fake transport in tests, not a scored API run.
- Whether an importance label would match every reviewer's judgment. Importance is a review-priority hint only.

Add a new labeled pair under `examples/documents/` when you need another situation to stay fixed. Keep the expected textual spans as the judge; do not promote heuristic explanations to ground truth.
