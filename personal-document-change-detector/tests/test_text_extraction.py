"""PDF and DOCX extraction helpers."""

from pathlib import Path

import pytest

from document_detector.docx_extractor import extract_docx
from document_detector.errors import ParseError
from document_detector.pdf_extractor import extract_pdf

ROOT = Path(__file__).resolve().parents[1]


def test_extract_pdf_roundtrip(tmp_path: Path):
    fitz = pytest.importorskip("fitz")
    path = tmp_path / "sample.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Notice period: 30 days.")
    document.save(path)
    document.close()
    pages, warnings = extract_pdf(path)
    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert "Notice period" in pages[0].text
    assert warnings == []


def test_extract_docx_headings(tmp_path: Path):
    Document = pytest.importorskip("docx").Document
    path = tmp_path / "sample.docx"
    document = Document()
    document.add_heading("Compensation", level=1)
    document.add_paragraph("Annual salary: €60,000.")
    document.save(path)
    pages, warnings = extract_docx(path)
    assert warnings == []
    text = pages[0].text
    assert "# Compensation" in text or "Compensation" in text
    assert "€60,000" in text


def test_encrypted_pdf(tmp_path: Path):
    fitz = pytest.importorskip("fitz")
    path = tmp_path / "locked.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "secret")
    document.save(path, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="owner")
    document.close()
    with pytest.raises(ParseError, match="encrypted"):
        extract_pdf(path)
