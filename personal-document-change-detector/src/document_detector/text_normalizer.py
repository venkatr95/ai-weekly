"""Normalize extracted document text without erasing meaningful symbols."""

from __future__ import annotations

import re
from collections import Counter

from document_detector.schemas import DocumentVersion, PageText
from document_detector.textutil import clean_text, collapse_spaces

_HEADER_CANDIDATE = re.compile(r"^[^\n]{3,80}$")


def normalize_pages(pages: list[PageText]) -> list[PageText]:
    return [
        PageText(page_number=page.page_number, text=normalize_page_text(page.text))
        for page in pages
    ]


def normalize_page_text(text: str) -> str:
    cleaned = clean_text(text)
    cleaned = collapse_spaces(cleaned)
    return cleaned


def strip_repeated_headers_footers(pages: list[PageText]) -> list[PageText]:
    """Remove short lines that repeat on most pages (likely headers/footers)."""

    if len(pages) < 3:
        return pages
    first_lines: list[str] = []
    last_lines: list[str] = []
    for page in pages:
        lines = [line.strip() for line in page.text.splitlines() if line.strip()]
        if not lines:
            continue
        if _HEADER_CANDIDATE.match(lines[0]):
            first_lines.append(lines[0])
        if len(lines) > 1 and _HEADER_CANDIDATE.match(lines[-1]):
            last_lines.append(lines[-1])
    threshold = max(2, len(pages) // 2)
    headers = {line for line, count in Counter(first_lines).items() if count >= threshold}
    footers = {line for line, count in Counter(last_lines).items() if count >= threshold}
    if not headers and not footers:
        return pages

    result: list[PageText] = []
    for page in pages:
        lines = [line for line in page.text.splitlines()]
        kept: list[str] = []
        for index, line in enumerate(lines):
            stripped = line.strip()
            if index == 0 and stripped in headers:
                continue
            if index == len(lines) - 1 and stripped in footers:
                continue
            kept.append(line)
        result.append(PageText(page_number=page.page_number, text="\n".join(kept).strip()))
    return result


def normalize_document(document: DocumentVersion) -> DocumentVersion:
    pages = normalize_pages(document.pages)
    pages = strip_repeated_headers_footers(pages)
    return document.model_copy(update={"pages": pages})
