"""Section parsing and alignment."""

from document_detector.document_aligner import align_sections
from document_detector.schemas import DocumentVersion, PageText
from document_detector.section_parser import parse_sections


def _doc(text: str) -> DocumentVersion:
    return DocumentVersion(
        document_id="d",
        filename="d.md",
        file_type="md",
        pages=[PageText(page_number=1, text=text)],
    )


def test_parse_markdown_headings():
    sections = parse_sections(
        _doc("# Title\n\nIntro\n\n## Compensation\n\nAnnual salary: €60,000.\n\n## Leave\n\n25 days.")
    )
    titles = [section.title for section in sections]
    assert "Compensation" in titles
    assert "Leave" in titles


def test_align_renamed_and_added_sections():
    previous = parse_sections(
        _doc("## Compensation\n\nPay is €60,000.\n\n## Leave\n\n25 days.")
    )
    updated = parse_sections(
        _doc("## Pay and Benefits\n\nPay is €65,000.\n\n## Leave\n\n25 days.\n\n## Remote Work\n\nOne day.")
    )
    pairs = align_sections(previous, updated)
    statuses = {pair.status for pair in pairs}
    assert "added" in statuses
    matched = [pair for pair in pairs if pair.previous and pair.updated]
    assert any(pair.status in {"matched", "renamed"} for pair in matched)
