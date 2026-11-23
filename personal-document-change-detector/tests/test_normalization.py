"""Normalization preserves meaningful symbols."""

from document_detector.schemas import DocumentVersion, PageText
from document_detector.text_normalizer import normalize_document, normalize_page_text


def test_normalize_keeps_currency_and_percent():
    text = normalize_page_text("Salary:   €60,000  (100%)\r\n\r\nNext")
    assert "€60,000" in text
    assert "100%" in text
    assert "\r" not in text


def test_strip_repeated_headers():
    pages = [
        PageText(page_number=1, text="Acme Corp\nBody one\nPage footer"),
        PageText(page_number=2, text="Acme Corp\nBody two\nPage footer"),
        PageText(page_number=3, text="Acme Corp\nBody three\nPage footer"),
    ]
    document = DocumentVersion(
        document_id="previous",
        filename="x.txt",
        file_type="txt",
        pages=pages,
    )
    normalized = normalize_document(document)
    joined = "\n".join(page.text for page in normalized.pages)
    assert "Acme Corp" not in joined
    assert "Page footer" not in joined
    assert "Body one" in joined
