"""Discover documents and extract text without executing anything inside them."""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

from evidence_agent.errors import EmptyCorpusError
from evidence_agent.schemas import DiscoveredFile, ExtractedDocument, PageText

logger = logging.getLogger("evidence_agent.ingestion")

SUPPORTED_SUFFIXES = {".pdf", ".txt", ".md", ".markdown"}
_OCR_TEXT_CHARS = 15


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def discover_files(root: Path) -> tuple[list[DiscoveredFile], list[str]]:
    """Return supported files and a list of skipped relative paths."""

    if not root.exists():
        raise EmptyCorpusError(
            f"Path does not exist: {root}. Pass a folder of PDF, Markdown, or text files."
        )
    supported: list[DiscoveredFile] = []
    skipped: list[str] = []
    candidates: list[Path] = []
    if root.is_file():
        candidates = [root]
        base = root.parent
    else:
        base = root
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(name for name in dirnames if not name.startswith(".") and name != "__pycache__")
            for name in sorted(filenames):
                if name.startswith("."):
                    continue
                candidates.append(Path(dirpath) / name)

    for path in candidates:
        suffix = path.suffix.lower()
        relative = path.name if root.is_file() else path.relative_to(base).as_posix()
        if suffix not in SUPPORTED_SUFFIXES:
            skipped.append(relative)
            continue
        supported.append(
            DiscoveredFile(absolute_path=str(path.resolve()), relative_path=relative, file_type=suffix.lstrip("."))
        )
    return supported, skipped


def _clean_text(text: str) -> str:
    return text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")


def _read_text_file(path: Path) -> str:
    data = path.read_bytes()
    if not data:
        return ""
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return _clean_text(data.decode(encoding))
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f"{path.name} is not valid UTF-8.")


def _load_fitz():
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF is required to read PDFs. Install dependencies with: pip install -r requirements.txt"
        ) from exc
    return fitz


def _extract_pdf(path: Path, relative_path: str, content_hash: str) -> ExtractedDocument:
    fitz = _load_fitz()
    pages: list[PageText] = []
    ocr_pages: list[int] = []
    try:
        document = fitz.open(path)
    except Exception as exc:
        return ExtractedDocument(
            absolute_path=str(path),
            relative_path=relative_path,
            file_type="pdf",
            content_hash=content_hash,
            error=f"Unreadable PDF ({exc.__class__.__name__}). The file was not indexed.",
        )
    try:
        if document.needs_pass:
            return ExtractedDocument(
                absolute_path=str(path),
                relative_path=relative_path,
                file_type="pdf",
                content_hash=content_hash,
                error="Encrypted PDF. Remove the password and index the file again. The file was not indexed.",
            )
        for index, page in enumerate(document, start=1):
            text = _clean_text(page.get_text("text") or "")
            images = page.get_images() or []
            drawings = page.get_drawings() or []
            needs_ocr = len(text.strip()) < _OCR_TEXT_CHARS and (bool(images) or bool(drawings))
            if needs_ocr:
                ocr_pages.append(index)
            pages.append(PageText(page_number=index, text=text, needs_ocr=needs_ocr))
    except Exception as exc:
        return ExtractedDocument(
            absolute_path=str(path),
            relative_path=relative_path,
            file_type="pdf",
            content_hash=content_hash,
            error=f"Failed to extract PDF text ({exc.__class__.__name__}). The file was not indexed.",
        )
    finally:
        document.close()

    char_count = sum(len(page.text.strip()) for page in pages)
    warning = None
    if ocr_pages and char_count < _OCR_TEXT_CHARS:
        warning = (
            f"No text layer on pages {ocr_pages}. This looks like a scan and requires OCR. "
            "Those pages were not indexed as searchable text."
        )
    elif ocr_pages:
        warning = (
            f"Pages {ocr_pages} have no text layer and may need OCR. "
            "Text from the other pages was indexed."
        )
    return ExtractedDocument(
        absolute_path=str(path),
        relative_path=relative_path,
        file_type="pdf",
        content_hash=content_hash,
        pages=pages,
        needs_ocr=bool(ocr_pages),
        ocr_pages=ocr_pages,
        warning=warning,
    )


def extract_file(path: Path, relative_path: str) -> ExtractedDocument:
    suffix = path.suffix.lower()
    file_type = "markdown" if suffix in {".md", ".markdown"} else suffix.lstrip(".")
    try:
        content_hash = hash_file(path)
    except OSError as exc:
        return ExtractedDocument(
            absolute_path=str(path),
            relative_path=relative_path,
            file_type=file_type,
            content_hash="",
            error=f"Could not read file ({exc.__class__.__name__}).",
        )

    if suffix == ".pdf":
        extracted = _extract_pdf(path, relative_path, content_hash)
    else:
        try:
            text = _read_text_file(path)
        except (OSError, UnicodeError) as exc:
            return ExtractedDocument(
                absolute_path=str(path),
                relative_path=relative_path,
                file_type=file_type,
                content_hash=content_hash,
                error=str(exc),
            )
        warning = None
        if not text.strip():
            warning = "File is empty. No searchable text was indexed."
        extracted = ExtractedDocument(
            absolute_path=str(path),
            relative_path=relative_path,
            file_type=file_type,
            content_hash=content_hash,
            pages=[PageText(page_number=None, text=text)],
            warning=warning,
        )

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "extracted %s chars=%s ocr=%s error=%s",
            relative_path,
            sum(len(page.text) for page in extracted.pages),
            extracted.needs_ocr,
            extracted.error,
        )
    return extracted
