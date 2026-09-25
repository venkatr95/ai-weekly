import pytest

from app.errors import EmptyDocument, InvalidDocument, UnsupportedDocument
from app.ingestion.parser import content_type_for_filename, parse_document
from app.sample_pdf import build_refund_policy_pdf


def test_extension_map():
    assert content_type_for_filename("notes.md") == "text/markdown"
    assert content_type_for_filename("notes.txt") == "text/plain"
    assert content_type_for_filename("policy.PDF") == "application/pdf"


def test_unsupported_extension():
    with pytest.raises(UnsupportedDocument):
        content_type_for_filename("sheet.docx")


def test_markdown_and_text_have_no_page():
    pages = parse_document("a.md", b"# Title\n\nHello", "text/markdown")
    assert len(pages) == 1
    assert pages[0].page is None
    assert "Hello" in pages[0].text


def test_text_must_be_utf8():
    with pytest.raises(InvalidDocument):
        parse_document("a.txt", b"\xff\xfe", "text/plain")


def test_empty_text_is_rejected():
    with pytest.raises(EmptyDocument):
        parse_document("a.txt", b"   ", "text/plain")


def test_refund_pdf_puts_the_rule_on_page_4():
    pages = parse_document("refund-policy.pdf", build_refund_policy_pdf(), "application/pdf")
    by_page = {page.page: page.text for page in pages}
    assert 4 in by_page
    assert "The refund period is 30 days." in by_page[4]
    assert all("refund period" not in text for number, text in by_page.items() if number != 4)
