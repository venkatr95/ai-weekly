"""Normalize an email body and separate signatures, disclaimers, and quote lines."""

from __future__ import annotations

import re

from email_to_action.textutil import normalize_whitespace

_CLOSING = re.compile(
    r"^(?:thanks|thank you|many thanks|best|best regards|kind regards|regards|sincerely|cheers|warmly|yours|talk soon),?\s*$",
    re.IGNORECASE,
)
_DISCLAIMER = re.compile(
    r"^(?:this (?:e-?mail|message) (?:and any attachments )?(?:is|are) (?:confidential|intended)|confidentiality notice|do not forward|unsubscribe\b)",
    re.IGNORECASE,
)
_GREETING = re.compile(r"^(?:hi|hello|dear|hey)\s+(?P<name>.+?)[,!]?\s*$", re.IGNORECASE)
_GENERIC_GREETING = {"there", "all", "everyone", "folks", "team"}


def prepare_body(body: str) -> tuple[str, str, str, str | None]:
    """Return body, quoted text, signature, and greeting name."""

    normalized = normalize_whitespace(body)
    without_quotes, quoted = peel_quote_lines(normalized)
    content, signature = split_signature(without_quotes)
    greeting = greeting_name(content)
    return content.strip(), quoted.strip(), signature.strip(), greeting


def peel_quote_lines(body: str) -> tuple[str, str]:
    kept: list[str] = []
    quoted: list[str] = []
    for line in body.split("\n"):
        stripped = line.lstrip()
        if stripped.startswith(">"):
            quoted.append(re.sub(r"^[ \t]*>[ \t]?", "", line))
        else:
            kept.append(line)
    return "\n".join(kept).strip(), "\n".join(quoted).strip()


def split_signature(body: str) -> tuple[str, str]:
    lines = body.split("\n")
    nonempty = [index for index, line in enumerate(lines) if line.strip()]
    cut = _closing_index(lines, nonempty)
    if cut is None:
        for index, line in enumerate(lines):
            if _DISCLAIMER.match(line.strip()):
                return "\n".join(lines[:index]).strip(), "\n".join(lines[index:]).strip()
        return body.strip(), ""
    return "\n".join(lines[:cut]).strip(), "\n".join(lines[cut:]).strip()


def signature_name(signature: str) -> str | None:
    lines = [line.strip(" ,") for line in signature.split("\n") if line.strip() and line.strip() != "--"]
    lines = [line for line in lines if not _CLOSING.match(line) and not _DISCLAIMER.match(line)]
    if not lines:
        return None
    candidate = lines[0]
    if len(candidate.split()) > 4 or "@" in candidate:
        return None
    return candidate


def greeting_name(body: str) -> str | None:
    for line in body.split("\n"):
        match = _GREETING.match(line.strip())
        if not match:
            continue
        name = match.group("name").strip()
        if name.lower() in _GENERIC_GREETING:
            return None
        return name
    return None


def _closing_index(lines: list[str], nonempty: list[int]) -> int | None:
    if len(nonempty) < 2:
        return None
    tail = set(nonempty[-8:])
    for index in nonempty:
        if index not in tail:
            continue
        if not (_CLOSING.match(lines[index].strip()) or lines[index].strip() == "--"):
            continue
        rest = [lines[later].strip() for later in nonempty if later > index]
        if len(rest) <= 5 and all(len(line) <= 80 and not _looks_like_request(line) for line in rest):
            return index
    return None


def _looks_like_request(line: str) -> bool:
    return bool(re.search(r"\b(please|could you|by|once)\b", line, re.IGNORECASE)) or line.endswith("?")
