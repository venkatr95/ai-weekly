"""Small text helpers shared across modules."""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE = re.compile(r"[ \t]+")
_MULTI_NEWLINE = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFKC", text)
    return text


def collapse_spaces(text: str) -> str:
    lines = [_WHITESPACE.sub(" ", line).strip() for line in text.splitlines()]
    return _MULTI_NEWLINE.sub("\n\n", "\n".join(lines)).strip()


def normalize_for_match(text: str) -> str:
    collapsed = collapse_spaces(text).lower()
    return re.sub(r"[^\w\s€$£¥%./:-]", "", collapsed)


def token_set(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9€$£¥%]+", normalize_for_match(text)) if token}


def jaccard(a: str, b: str) -> float:
    left = token_set(a)
    right = token_set(b)
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def contains_quote(haystack: str, quote: str) -> bool:
    if not quote or not quote.strip():
        return False
    if quote in haystack:
        return True
    return normalize_for_match(quote) in normalize_for_match(haystack)
