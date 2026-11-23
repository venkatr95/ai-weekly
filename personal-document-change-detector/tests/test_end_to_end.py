"""End-to-end comparison against the employment agreement sample."""

import json
from pathlib import Path

from document_detector.config import Settings
from document_detector.pipeline import compare
from document_detector.report_generator import render_json, render_markdown

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "documents"


def test_employment_agreement_detects_key_changes():
    report = compare(
        EXAMPLES / "employment_v1.md",
        EXAMPLES / "employment_v2.md",
        settings=Settings(provider="heuristic"),
    )
    assert report.summary.total_changes >= 3
    blob = " ".join(
        filter(
            None,
            [c.previous_text for c in report.changes] + [c.updated_text for c in report.changes],
        )
    )
    assert "€60,000" in blob
    assert "€65,000" in blob
    assert "30 days" in blob
    assert "90 days" in blob
    assert "three days" in blob.lower() or "3 days" in blob.lower() or "one day" in blob.lower()
    assert all(change.evidence_validated for change in report.changes)
    assert report.review_recommendations
    assert "not legal" in report.disclaimer.lower()

    markdown = render_markdown(report)
    assert "Document comparison summary" in markdown
    payload = json.loads(render_json(report))
    assert payload["summary"]["total_changes"] == report.summary.total_changes
    assert payload["provider"] == "heuristic"


def test_min_importance_filters(tmp_path: Path):
    report = compare(
        EXAMPLES / "employment_v1.md",
        EXAMPLES / "employment_v2.md",
        settings=Settings(provider="heuristic"),
        min_importance="high",
    )
    assert all(change.importance in {"critical", "high"} for change in report.changes)


def test_supplier_obligation_and_addition():
    report = compare(
        EXAMPLES / "supplier_v1.md",
        EXAMPLES / "supplier_v2.md",
        settings=Settings(provider="heuristic"),
    )
    texts = " ".join(
        filter(None, [c.previous_text for c in report.changes] + [c.updated_text for c in report.changes] + [c.explanation for c in report.changes])
    ).lower()
    assert "shall" in texts or "should" in texts or "weakened" in texts
    assert any(change.change_type == "added" for change in report.changes) or "confidential" in texts
