"""Split one document into overlapping chunks. Chunks never cross documents."""

from __future__ import annotations

import hashlib
import re

from evidence_agent.errors import ConfigurationError
from evidence_agent.schemas import Chunk, ExtractedDocument, PageSpan

_TOKEN_SPAN = re.compile(r"\S+")


def document_id_for(relative_path: str) -> str:
    return hashlib.sha256(relative_path.encode("utf-8")).hexdigest()[:16]


def chunk_id_for(relative_path: str, ordinal: int, text: str) -> str:
    payload = f"{relative_path}\n{ordinal}\n{text}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:20]


def _joined_text(document: ExtractedDocument) -> tuple[str, list[PageSpan]]:
    parts: list[str] = []
    spans: list[PageSpan] = []
    cursor = 0
    for page in document.pages:
        text = page.text.strip()
        if not text:
            continue
        if parts:
            parts.append("\n\n")
            cursor += 2
        start = cursor
        parts.append(text)
        cursor += len(text)
        spans.append(PageSpan(start=start, end=cursor, page=page.page_number))
    return "".join(parts), spans


def _spans_for_slice(spans: list[PageSpan], start: int, end: int) -> list[PageSpan]:
    sliced: list[PageSpan] = []
    for span in spans:
        overlap_start = max(span.start, start)
        overlap_end = min(span.end, end)
        if overlap_start < overlap_end:
            sliced.append(
                PageSpan(start=overlap_start - start, end=overlap_end - start, page=span.page)
            )
    return sliced


def chunk_document(document: ExtractedDocument, chunk_size: int, chunk_overlap: int) -> list[Chunk]:
    if chunk_size < 1:
        raise ConfigurationError("Chunk size must be at least 1 token.")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ConfigurationError("Chunk overlap must be smaller than chunk size.")
    if document.error:
        return []

    text, page_spans = _joined_text(document)
    if not text.strip():
        return []

    tokens = list(_TOKEN_SPAN.finditer(text))
    if not tokens:
        return []

    doc_id = document_id_for(document.relative_path)
    chunks: list[Chunk] = []
    start_token = 0
    ordinal = 0
    token_count = len(tokens)
    while start_token < token_count:
        end_token = min(start_token + chunk_size, token_count)
        char_start = tokens[start_token].start()
        char_end = tokens[end_token - 1].end()
        piece = text[char_start:char_end]
        spans = _spans_for_slice(page_spans, char_start, char_end)
        pages = [span.page for span in spans if span.page is not None]
        chunks.append(
            Chunk(
                chunk_id=chunk_id_for(document.relative_path, ordinal, piece),
                document_id=doc_id,
                relative_path=document.relative_path,
                text=piece,
                page_start=pages[0] if pages else None,
                page_end=pages[-1] if pages else None,
                page_spans=spans,
                ordinal=ordinal,
            )
        )
        ordinal += 1
        if end_token == token_count:
            break
        next_start = end_token - chunk_overlap
        if next_start <= start_token:
            next_start = start_token + 1
        start_token = next_start
    return chunks
