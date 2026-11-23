"""Extract text from PDF files with page numbers. Does not execute file contents."""

from __future__ import annotations

from pathlib import Path

from document_detector.errors import ParseError
from document_detector.schemas import PageText
from document_detector.textutil import clean_text

_OCR_TEXT_CHARS = 15


def extract_pdf(path: Path) -> tuple[list[PageText], list[str]]:
    """Return page texts and warnings. Page numbers start at 1."""

    try:
        import fitz
    except ImportError as exc:
        raise ParseError(
            "PyMuPDF is required to read PDFs. Install dependencies with: pip install -r requirements.txt"
        ) from exc

    try:
        document = fitz.open(path)
    except Exception as exc:
        raise ParseError(
            f"Could not read '{path.name}': unreadable PDF ({exc.__class__.__name__})."
        ) from exc

    pages: list[PageText] = []
    warnings: list[str] = []
    try:
        if document.needs_pass:
            raise ParseError(
                f"Could not read '{path.name}': the PDF is encrypted. Remove the password and try again."
            )
        ocr_pages: list[int] = []
        for index, page in enumerate(document, start=1):
            text = clean_text(page.get_text("text") or "")
            images = page.get_images() or []
            drawings = page.get_drawings() or []
            if len(text.strip()) < _OCR_TEXT_CHARS and (images or drawings):
                ocr_pages.append(index)
            pages.append(PageText(page_number=index, text=text))
    except ParseError:
        raise
    except Exception as exc:
        raise ParseError(
            f"Could not read '{path.name}': PDF text extraction failed ({exc.__class__.__name__})."
        ) from exc
    finally:
        document.close()

    if ocr_pages:
        rendered = ", ".join(str(number) for number in ocr_pages)
        warnings.append(
            f"'{path.name}' has no text layer on page(s) {rendered}. "
            "Those pages look like scans and were not OCR'd."
        )
    if not any(page.text.strip() for page in pages):
        warnings.append(f"'{path.name}' has no extractable text.")
    return pages, warnings
