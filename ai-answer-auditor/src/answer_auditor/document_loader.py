"""Load answer text and source documents from files, directories, or JSON."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from answer_auditor.errors import InputError, ParseError
from answer_auditor.schemas import AuditRequest, PageText, SourceDocument
from answer_auditor.text_extractor import (
    clean_text,
    extract_json_text,
    extract_pdf,
    read_text_file,
)

SUPPORTED_SUFFIXES = {".txt", ".md", ".markdown", ".pdf", ".json"}
_TITLE_LINE = re.compile(r"^Title:\s*(.+?)\s*$", re.IGNORECASE)
_MARKDOWN_TITLE = re.compile(r"^#\s+(.+?)\s*$")


def read_answer(path: Path) -> str:
    if not path.is_file():
        raise InputError(f"Answer file not found: {path}")
    if path.suffix.lower() not in {".txt", ".md", ".markdown"}:
        raise InputError(
            f"Unsupported answer file '{path.name}'. Use a .txt or .md file, or pass JSON with --input."
        )
    text = read_text_file(path).strip()
    if not text:
        raise InputError(f"The answer file '{path.name}' is empty.")
    return text


def load_request(path: Path) -> AuditRequest:
    if not path.is_file():
        raise InputError(f"Input file not found: {path}")
    try:
        payload = json.loads(read_text_file(path))
    except json.JSONDecodeError as exc:
        raise InputError(f"Could not read '{path.name}': invalid JSON ({exc.msg}).") from exc
    except ParseError as exc:
        raise InputError(str(exc)) from exc
    if not isinstance(payload, dict):
        raise InputError(f"'{path.name}' must be a JSON object with an answer and sources.")
    try:
        request = AuditRequest.model_validate(payload)
    except Exception as exc:
        raise InputError(
            f"'{path.name}' must include an answer string and a sources array."
        ) from exc
    if not request.answer.strip():
        raise InputError(f"The answer in '{path.name}' is empty.")
    if not request.sources:
        raise InputError(f"'{path.name}' does not list any sources.")
    return request


def _split_title(text: str, file_type: str) -> tuple[str | None, str]:
    lines = text.splitlines()
    start = 0
    while start < len(lines) and not lines[start].strip():
        start += 1
    if start >= len(lines):
        return None, ""
    title_match = _TITLE_LINE.match(lines[start].strip())
    if title_match:
        body = "\n".join(lines[start + 1 :]).strip()
        return title_match.group(1).strip(), body
    if file_type in {"md", "markdown"}:
        heading = _MARKDOWN_TITLE.match(lines[start].strip())
        if heading:
            body = "\n".join(lines[start + 1 :]).strip()
            return heading.group(1).strip(), body
    return None, text.strip()


def _source_id(index: int, requested: str | None) -> str:
    if requested and re.fullmatch(r"[A-Za-z0-9_-]{1,32}", requested):
        return requested
    return f"S{index}"


def _document_from_text(
    *,
    source_id: str,
    title: str | None,
    path: str | None,
    file_type: str,
    text: str,
    warnings: list[str],
) -> SourceDocument:
    parsed_title, body = _split_title(text, file_type)
    pages = [PageText(page_number=None, text=body)]
    if not body.strip():
        warnings = [*warnings, f"'{path or source_id}' has no extractable text."]
    resolved = title or parsed_title
    if resolved is None and path:
        resolved = Path(path).stem
    return SourceDocument(
        source_id=source_id,
        title=resolved,
        path=path,
        file_type=file_type,
        pages=pages,
        warnings=warnings,
    )


def _load_path(path: Path, source_id: str, title: str | None) -> SourceDocument:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ParseError(
            f"Unsupported source type '{suffix or path.name}'. "
            "Supported types: .txt, .md, .markdown, .pdf, .json."
        )
    if not path.is_file():
        raise ParseError(f"Source file not found: {path}")
    display_path = path.as_posix()
    if suffix == ".pdf":
        pages, warnings = extract_pdf(path)
        body_title, _ = _split_title("\n\n".join(page.text for page in pages), "txt")
        return SourceDocument(
            source_id=source_id,
            title=title or body_title or path.stem,
            path=display_path,
            file_type="pdf",
            pages=pages,
            warnings=warnings,
        )
    if suffix == ".json":
        json_title, text, warnings = extract_json_text(path)
        return _document_from_text(
            source_id=source_id,
            title=title or json_title,
            path=display_path,
            file_type="json",
            text=text,
            warnings=warnings,
        )
    file_type = "md" if suffix in {".md", ".markdown"} else "txt"
    text = read_text_file(path)
    return _document_from_text(
        source_id=source_id,
        title=title,
        path=display_path,
        file_type=file_type,
        text=text,
        warnings=[],
    )


def _discover(root: Path) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if not name.startswith(".") and name != "__pycache__")
        for name in sorted(filenames):
            if name.startswith("."):
                continue
            found.append(Path(dirpath) / name)
    return found


def load_sources(entries: list[Path | str | dict]) -> tuple[list[SourceDocument], list[str]]:
    """Load sources in the order they were given.

    A directory contributes its supported files in sorted order. Unsupported
    files inside a directory are skipped with a warning. An explicitly named
    unsupported file is an error.
    """

    if not entries:
        raise InputError("Provide at least one source file or directory.")

    documents: list[SourceDocument] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()

    def add(document: SourceDocument) -> None:
        if document.source_id in seen_ids:
            raise InputError(f"Duplicate source id '{document.source_id}'.")
        seen_ids.add(document.source_id)
        documents.append(document)
        warnings.extend(document.warnings)

    next_index = 1
    for entry in entries:
        if isinstance(entry, dict):
            source_id = _source_id(next_index, _as_str(entry.get("source_id") or entry.get("id")))
            title = _as_str(entry.get("title"))
            inline = entry.get("text")
            raw_path = entry.get("path")
            if isinstance(inline, str) and inline.strip():
                file_type = _as_str(entry.get("file_type")) or "txt"
                add(
                    _document_from_text(
                        source_id=source_id,
                        title=title,
                        path=_as_str(raw_path),
                        file_type=file_type,
                        text=clean_text(inline),
                        warnings=[],
                    )
                )
                next_index += 1
                continue
            if not raw_path:
                raise InputError(
                    f"Source '{source_id}' needs a text field or a path."
                )
            add(_load_path(Path(str(raw_path)), source_id, title))
            next_index += 1
            continue

        path = Path(entry)
        if path.is_dir():
            children = _discover(path)
            if not children:
                raise InputError(f"Source directory is empty: {path}")
            supported = [child for child in children if child.suffix.lower() in SUPPORTED_SUFFIXES]
            for child in children:
                if child.suffix.lower() not in SUPPORTED_SUFFIXES:
                    relative = child.relative_to(path).as_posix()
                    warnings.append(f"Skipped unsupported file: {relative}")
            if not supported:
                raise InputError(
                    f"No supported sources in {path}. Supported types: .txt, .md, .markdown, .pdf, .json."
                )
            for child in supported:
                source_id = _source_id(next_index, None)
                add(_load_path(child, source_id, None))
                next_index += 1
            continue

        source_id = _source_id(next_index, None)
        add(_load_path(path, source_id, None))
        next_index += 1

    usable = [document for document in documents if document.full_text().strip()]
    if not usable:
        detail = " ".join(warnings) or "Every source was empty."
        raise InputError(f"No source text could be extracted. {detail}")
    return documents, warnings


def _as_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
