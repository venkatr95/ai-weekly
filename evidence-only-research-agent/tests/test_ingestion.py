from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from evidence_agent.errors import EmptyCorpusError
from evidence_agent.ingestion import discover_files, extract_file
from evidence_agent.pipeline import ResearchPipeline
from helpers import build_settings, write_corpus
from pdf_util import write_text_pdf


def test_discovers_nested_text_and_skips_unknown_types(tmp_path: Path) -> None:
    root = write_corpus(
        tmp_path / "docs",
        {
            "notes/unicode_notes.md": "Researcher Søren Lind reviewed the protocol yesterday.",
            "plain.TXT": "A plain text file with café in the body of the note.",
            "notes/ignore.dat": "skip",
        },
    )
    supported, skipped = discover_files(root)
    relatives = {item.relative_path for item in supported}
    assert relatives == {"notes/unicode_notes.md", "plain.TXT"}
    assert skipped == ["notes/ignore.dat"]


def test_extracts_unicode_and_pdf_pages(tmp_path: Path) -> None:
    text_path = tmp_path / "note.md"
    text_path.write_text("Researcher Søren Lind reviewed the protocol in Malmö.\n", encoding="utf-8")
    extracted = extract_file(text_path, "note.md")
    assert "Søren" in extracted.text
    assert "Malmö" in extracted.text
    assert extracted.error is None

    pdf_path = tmp_path / "paper.pdf"
    write_text_pdf(
        pdf_path,
        [
            "Page one introduces the catalog and nothing more.",
            "Page two states that the primary marker is cobalt blue.",
        ],
    )
    pdf = extract_file(pdf_path, "paper.pdf")
    assert pdf.error is None
    assert [page.page_number for page in pdf.pages] == [1, 2]
    assert "cobalt blue" in pdf.pages[1].text
    assert "Page one" not in pdf.pages[1].text


def test_corrupt_empty_and_scanned_files_are_reported(tmp_path: Path, caplog) -> None:
    root = tmp_path / "docs"
    root.mkdir()
    (root / "empty.txt").write_text("", encoding="utf-8")
    (root / "broken.pdf").write_bytes(b"%PDF-1.4\nthis is not a pdf")
    (root / "ok.txt").write_text(
        "The readable note says the archive code is silver lantern.\n",
        encoding="utf-8",
    )
    document = fitz.open()
    page = document.new_page()
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 16, 16), 1)
    pixmap.clear_with(200)
    page.insert_image(fitz.Rect(72, 72, 180, 180), pixmap=pixmap)
    document.save(root / "scan.pdf")
    document.close()

    pipeline = ResearchPipeline(build_settings(tmp_path))
    with caplog.at_level("DEBUG", logger="evidence_agent"):
        report = pipeline.index_path(root, rebuild=True)
    assert report.stats.files_failed >= 1
    assert report.stats.files_empty >= 1
    assert report.stats.files_needs_ocr >= 1
    assert any("broken.pdf" in error for error in report.errors)
    assert any("scan.pdf" in warning for warning in report.ocr_warnings)
    assert "silver lantern" not in caplog.text
    readable = next(document for document in pipeline.store.documents if document.relative_path == "ok.txt")
    assert readable.error is None
    assert readable.chunk_ids


def test_empty_folder_raises(tmp_path: Path) -> None:
    folder = tmp_path / "empty"
    folder.mkdir()
    pipeline = ResearchPipeline(build_settings(tmp_path))
    with pytest.raises(EmptyCorpusError):
        pipeline.index_path(folder, rebuild=True)
