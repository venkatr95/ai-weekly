"""Extract text from PDF, Markdown, plain text, and JSON sources.

Extraction reads bytes and returns text. It does not execute file contents.
"""

from __future__ import annotations

import json
from pathlib import Path

from answer_auditor.errors import ParseError
from answer_auditor.schemas import PageText

_OCR_TEXT_CHARS = 15


def clean_text(text: str) -> str:
    return text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")


def read_text_file(path: Path) -> str:
    data = path.read_bytes()
    if not data:
        return ""
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return clean_text(data.decode(encoding))
        except UnicodeDecodeError:
            continue
    raise ParseError(f"Could not read '{path.name}': the file is not valid UTF-8.")


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
            "Those pages look like scans and were not OCR'd, so claims cannot be checked against them."
        )
    if not any(page.text.strip() for page in pages):
        warnings.append(f"'{path.name}' has no extractable text.")
    return pages, warnings


def extract_json_text(path: Path) -> tuple[str | None, str, list[str]]:
    """Read one JSON source document. Returns title, text, warnings."""

    raw = read_text_file(path)
    if not raw.strip():
        raise ParseError(f"Could not read '{path.name}': the JSON file is empty.")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ParseError(f"Could not read '{path.name}': invalid JSON ({exc.msg}).") from exc
    if isinstance(payload, str):
        return None, clean_text(payload), []
    if not isinstance(payload, dict):
        raise ParseError(
            f"Could not read '{path.name}': a JSON source must be an object with a text field."
        )
    title = payload.get("title") or payload.get("source_title")
    text = payload.get("text")
    if text is None and isinstance(payload.get("pages"), list):
        text = "\n\n".join(str(page) for page in payload["pages"])
    if not isinstance(text, str) or not text.strip():
        raise ParseError(
            f"Could not read '{path.name}': a JSON source must contain a non-empty text field."
        )
    if title is not None and not isinstance(title, str):
        title = str(title)
    return title, clean_text(text), []
