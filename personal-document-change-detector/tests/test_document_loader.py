"""Document loading for supported and unsupported files."""

from pathlib import Path

import pytest

from document_detector.document_loader import load_document, load_pair
from document_detector.errors import InputError

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "documents"


def test_load_markdown_pair():
    previous, updated = load_pair(EXAMPLES / "employment_v1.md", EXAMPLES / "employment_v2.md")
    assert previous.document_id == "previous"
    assert updated.document_id == "updated"
    assert "€60,000" in previous.full_text()
    assert "€65,000" in updated.full_text()


def test_unsupported_and_missing(tmp_path: Path):
    bad = tmp_path / "notes.csv"
    bad.write_text("a,b\n", encoding="utf-8")
    with pytest.raises(InputError, match="Unsupported"):
        load_document(bad, "previous")
    with pytest.raises(InputError, match="not found"):
        load_document(tmp_path / "missing.txt", "previous")


def test_empty_file(tmp_path: Path):
    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(InputError, match="No text"):
        load_document(empty, "previous")
