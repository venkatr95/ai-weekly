"""Extract text from PDF, TXT, and Markdown uploads.

PDF pages stay separate so a citation can name the page the text came from.
TXT and Markdown have no pages.
"""

from dataclasses import dataclass
from pathlib import Path

import pymupdf

from app.errors import EmptyDocument, InvalidDocument, UnsupportedDocument

PDF = "application/pdf"
TEXT = "text/plain"
MARKDOWN = "text/markdown"

_EXTENSIONS = {
    ".pdf": PDF,
    ".txt": TEXT,
    ".md": MARKDOWN,
    ".markdown": MARKDOWN,
}


@dataclass(frozen=True)
class ParsedPage:
    page: int | None
    text: str


def content_type_for_filename(filename: str) -> str:
    extension = Path(filename).suffix.lower()
    try:
        return _EXTENSIONS[extension]
    except KeyError as exc:
        label = extension or filename
        raise UnsupportedDocument(
            f"Unsupported file type '{label}'. Upload a PDF, TXT, or Markdown file."
        ) from exc


def parse_document(filename: str, data: bytes, content_type: str) -> list[ParsedPage]:
    if content_type == PDF:
        return _parse_pdf(data)
    if content_type in {TEXT, MARKDOWN}:
        return [ParsedPage(page=None, text=_decode_text(data))]
    raise UnsupportedDocument(
        f"Unsupported content type '{content_type}' for '{filename}'."
    )


def _decode_text(data: bytes) -> str:
    if not data.strip():
        raise EmptyDocument("Document is empty")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InvalidDocument("Text documents must be UTF-8") from exc
    text = text.replace("\x00", "").strip()
    if not text:
        raise EmptyDocument("Document contained no extractable text")
    return text


def _parse_pdf(data: bytes) -> list[ParsedPage]:
    if not data:
        raise EmptyDocument("Document is empty")
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise InvalidDocument("Could not read PDF") from exc
    pages: list[ParsedPage] = []
    try:
        for number, page in enumerate(document, start=1):
            # Visual line breaks are not sentence breaks. Collapse them so a
            # policy sentence that wraps on the page stays one searchable string.
            text = " ".join(page.get_text("text").replace("\x00", "").split())
            if text:
                pages.append(ParsedPage(page=number, text=text))
    finally:
        document.close()
    if not pages:
        raise EmptyDocument("Document contained no extractable text")
    return pages
