"""Deterministic text diff behavior."""

from document_detector.document_aligner import align_sections
from document_detector.schemas import DocumentVersion, PageText
from document_detector.section_parser import parse_sections
from document_detector.text_diff import _formatting_only, diff_aligned_sections


def _sections(text: str):
    document = DocumentVersion(
        document_id="d",
        filename="d.md",
        file_type="md",
        pages=[PageText(page_number=1, text=text)],
    )
    return parse_sections(document)


def test_detect_modified_paragraph():
    previous = _sections("## Salary\n\nAnnual salary: €60,000.")
    updated = _sections("## Salary\n\nAnnual salary: €65,000.")
    changes = diff_aligned_sections(align_sections(previous, updated))
    assert any(change.change_type == "modified" for change in changes)
    modified = next(change for change in changes if change.change_type == "modified")
    assert "€60,000" in (modified.previous_text or "")
    assert "€65,000" in (modified.updated_text or "")


def test_formatting_only_flag():
    assert _formatting_only("Hello   world", "Hello world")
    assert not _formatting_only("Hello world", "Hello worlds")
