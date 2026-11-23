"""Extract text from DOCX files. Does not execute macros or embedded scripts."""

from __future__ import annotations

from pathlib import Path

from document_detector.errors import ParseError
from document_detector.schemas import PageText
from document_detector.textutil import clean_text


def extract_docx(path: Path) -> tuple[list[PageText], list[str]]:
    try:
        from docx import Document
    except ImportError as exc:
        raise ParseError(
            "python-docx is required to read Word documents. "
            "Install dependencies with: pip install -r requirements.txt"
        ) from exc

    try:
        document = Document(str(path))
    except Exception as exc:
        raise ParseError(
            f"Could not read '{path.name}': unreadable DOCX ({exc.__class__.__name__})."
        ) from exc

    chunks: list[str] = []
    warnings: list[str] = []
    try:
        for paragraph in document.paragraphs:
            text = clean_text(paragraph.text or "")
            if text.strip():
                style = (paragraph.style.name or "") if paragraph.style else ""
                if style.startswith("Heading"):
                    level = "".join(ch for ch in style if ch.isdigit()) or "1"
                    prefix = "#" * min(int(level), 6)
                    chunks.append(f"{prefix} {text.strip()}")
                else:
                    chunks.append(text.strip())
        for table in document.tables:
            for row in table.rows:
                cells = [clean_text(cell.text or "").strip() for cell in row.cells]
                cells = [cell for cell in cells if cell]
                if cells:
                    chunks.append(" | ".join(cells))
    except Exception as exc:
        raise ParseError(
            f"Could not read '{path.name}': DOCX text extraction failed ({exc.__class__.__name__})."
        ) from exc

    body = "\n\n".join(chunks).strip()
    if not body:
        warnings.append(f"'{path.name}' has no extractable text.")
    return [PageText(page_number=None, text=body)], warnings
