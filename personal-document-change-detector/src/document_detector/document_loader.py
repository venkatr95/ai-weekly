"""Load previous and updated document versions from files."""

from __future__ import annotations

from pathlib import Path

from document_detector.docx_extractor import extract_docx
from document_detector.errors import InputError, ParseError
from document_detector.pdf_extractor import extract_pdf
from document_detector.schemas import DocumentVersion, PageText
from document_detector.textutil import clean_text

SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt", ".md", ".markdown"}


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


def load_document(path: Path, document_id: str) -> DocumentVersion:
    if not path.exists():
        raise InputError(f"Document not found: {path}")
    if not path.is_file():
        raise InputError(f"Expected a file, got a directory: {path}")
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise InputError(
            f"Unsupported document type '{suffix or path.name}'. "
            "Supported types: .pdf, .docx, .txt, .md, .markdown."
        )

    display = path.as_posix()
    filename = path.name
    if suffix == ".pdf":
        pages, warnings = extract_pdf(path)
        file_type = "pdf"
    elif suffix == ".docx":
        pages, warnings = extract_docx(path)
        file_type = "docx"
    else:
        text = read_text_file(path)
        pages = [PageText(page_number=None, text=text)]
        warnings = []
        file_type = "md" if suffix in {".md", ".markdown"} else "txt"
        if not text.strip():
            warnings.append(f"'{filename}' is empty.")

    document = DocumentVersion(
        document_id=document_id,
        filename=filename,
        path=display,
        file_type=file_type,
        pages=pages,
        warnings=warnings,
    )
    if not document.full_text().strip():
        detail = " ".join(warnings) or "The file has no extractable text."
        raise InputError(f"No text could be extracted from '{filename}'. {detail}")
    return document


def load_pair(old_path: Path, new_path: Path) -> tuple[DocumentVersion, DocumentVersion]:
    previous = load_document(old_path, "previous")
    updated = load_document(new_path, "updated")
    return previous, updated
