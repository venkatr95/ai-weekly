"""The web UI uses the same comparison pipeline as the CLI."""

from pathlib import Path

import pytest

from document_detector.errors import DetectorError
from streamlit_app import change_rows, compare_paths, compare_uploads

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / "examples" / "documents" / "employment_v1.md"
NEW = ROOT / "examples" / "documents" / "employment_v2.md"


def test_example_rows():
    report = compare_paths(
        OLD,
        NEW,
        provider="heuristic",
        min_importance="informational",
        include_formatting=False,
    )
    rows = change_rows(report)
    assert rows
    assert rows[0]["ID"].startswith("CH")
    assert any("€65,000" in row["Updated"] or "90" in row["Updated"] for row in rows)


def test_upload_compare_and_bad_type():
    report = compare_uploads(
        "employment_v1.md",
        OLD.read_bytes(),
        "employment_v2.md",
        NEW.read_bytes(),
        provider="heuristic",
        min_importance="informational",
        include_formatting=False,
    )
    assert report.summary.total_changes >= 3

    with pytest.raises(DetectorError):
        compare_uploads(
            "old.csv",
            b"a,b\n",
            "new.csv",
            b"a,c\n",
            provider="heuristic",
            min_importance="informational",
            include_formatting=False,
        )
