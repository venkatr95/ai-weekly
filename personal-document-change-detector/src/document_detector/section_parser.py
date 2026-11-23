"""Split documents into headed sections and paragraphs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from document_detector.schemas import DocumentVersion, PageText

_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_NUMBERED_HEADING = re.compile(
    r"^(?:section\s+)?(\d+(?:\.\d+){0,3}|[A-Z]|[IVXLC]+)\s*[.):\-–—]\s+(.+)$",
    re.IGNORECASE,
)
_ALL_CAPS_HEADING = re.compile(r"^[A-Z][A-Z0-9 /&-]{2,60}$")
_TITLE_CASE_SHORT = re.compile(r"^[A-Z][A-Za-z0-9 ,/&-]{2,60}$")


@dataclass
class Paragraph:
    text: str
    page: int | None = None


@dataclass
class Section:
    title: str
    level: int
    paragraphs: list[Paragraph] = field(default_factory=list)
    page: int | None = None

    def body(self) -> str:
        return "\n\n".join(p.text for p in self.paragraphs if p.text.strip())

    def full_text(self) -> str:
        body = self.body()
        if self.title == "(Document)":
            return body
        if body:
            return f"{self.title}\n\n{body}"
        return self.title


def parse_sections(document: DocumentVersion) -> list[Section]:
    sections: list[Section] = []
    current = Section(title="(Document)", level=0, page=_first_page(document.pages))

    for page in document.pages:
        for block in _blocks(page.text):
            heading = _as_heading(block)
            if heading is not None:
                title, level = heading
                if current.paragraphs or current.title != "(Document)":
                    sections.append(current)
                current = Section(title=title, level=level, page=page.page_number)
                continue
            current.paragraphs.append(Paragraph(text=block, page=page.page_number))
            if current.page is None:
                current.page = page.page_number

    if current.paragraphs or current.title != "(Document)" or not sections:
        sections.append(current)
    return sections


def _first_page(pages: list[PageText]) -> int | None:
    for page in pages:
        if page.page_number is not None:
            return page.page_number
    return None


def _blocks(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n", text.strip()) if text.strip() else []
    blocks: list[str] = []
    for part in parts:
        lines = [line.rstrip() for line in part.splitlines() if line.strip()]
        if not lines:
            continue
        if len(lines) == 1:
            blocks.append(lines[0].strip())
            continue
        # Keep multi-line paragraphs together unless every line looks like a heading.
        blocks.append("\n".join(lines).strip())
    return blocks


def _as_heading(block: str) -> tuple[str, int] | None:
    if "\n" in block:
        return None
    line = block.strip()
    md = _MD_HEADING.match(line)
    if md:
        return md.group(2).strip(), len(md.group(1))
    numbered = _NUMBERED_HEADING.match(line)
    if numbered:
        return numbered.group(2).strip(), 1 + numbered.group(1).count(".")
    if _ALL_CAPS_HEADING.match(line) and not line.endswith("."):
        return line.title() if line.isupper() else line, 1
    if (
        _TITLE_CASE_SHORT.match(line)
        and len(line.split()) <= 8
        and not line.endswith((".", ":", ";"))
        and not any(ch.isdigit() for ch in line)
    ):
        # Avoid treating ordinary short sentences as headings.
        words = line.split()
        if words and all(word[:1].isupper() for word in words if word[0].isalpha()):
            return line, 2
    return None
