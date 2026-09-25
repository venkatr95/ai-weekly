"""Split extracted text into overlapping token windows.

Tokens are words and punctuation marks, not model-specific byte pieces. The
window is about 500 of those tokens, with about 100 tokens of overlap, and both
values are configurable.

PDF pages are chunked separately. A chunk never crosses a page boundary, so the
page stored on the chunk is the page that contains its text.
"""

import re
from dataclasses import dataclass

from app.ingestion.parser import ParsedPage

_TOKEN = re.compile(r"\w+|[^\w\s]", re.UNICODE)


@dataclass(frozen=True)
class TextChunk:
    text: str
    page: int | None
    chunk_index: int
    token_count: int


class Chunker:
    def __init__(self, chunk_size: int, overlap: int) -> None:
        if chunk_size < 1:
            raise ValueError("chunk_size must be positive")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be >= 0 and smaller than chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, pages: list[ParsedPage]) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        for page in pages:
            for text, token_count in self._windows(page.text):
                chunks.append(
                    TextChunk(
                        text=text,
                        page=page.page,
                        chunk_index=len(chunks),
                        token_count=token_count,
                    )
                )
        return chunks

    def _windows(self, text: str) -> list[tuple[str, int]]:
        spans = [(match.start(), match.end()) for match in _TOKEN.finditer(text)]
        count = len(spans)
        if count == 0:
            return []
        if count <= self.chunk_size:
            snippet = text[spans[0][0] : spans[-1][1]].strip()
            return [(snippet, count)] if snippet else []

        step = self.chunk_size - self.overlap
        windows: list[tuple[str, int]] = []
        start = 0
        while start < count:
            end = min(start + self.chunk_size, count)
            # The next window is already fully covered by the previous one.
            if start > 0 and end <= start + self.overlap:
                break
            snippet = text[spans[start][0] : spans[end - 1][1]].strip()
            if snippet:
                windows.append((snippet, end - start))
            if end == count:
                break
            start += step
        return windows
