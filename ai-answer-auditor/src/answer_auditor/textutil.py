"""Token, whitespace, and quote helpers.

Source text is data. These helpers never evaluate it.
"""

from __future__ import annotations

import re

STOPWORDS = frozenset(
    {
        "a", "an", "the", "of", "and", "or", "to", "in", "on", "for", "with",
        "by", "from", "that", "this", "these", "those", "is", "are", "was",
        "were", "be", "been", "being", "as", "at", "it", "its", "their", "his",
        "her", "they", "them", "what", "which", "how", "why", "who", "when",
        "where", "do", "does", "did", "about", "into", "than", "then", "there",
        "have", "has", "had", "can", "could", "should", "would", "may", "might",
        "will", "shall", "also", "such", "using", "used", "use", "between",
        "both", "each", "other", "any", "all", "some", "nor", "so", "if", "but",
        "we", "our", "you", "your", "he", "she", "per", "via", "within",
        "without", "over", "under", "after", "before", "during", "while",
        "because", "due", "only", "more", "most", "less", "very", "just", "not",
        "no", "many", "much", "its", "end", "compared", "amounted", "achieved",
        "generated", "reported", "company", "financial", "year",
    }
)

_TOKEN = re.compile(r"[\w]+", flags=re.UNICODE)
_E_RESTORE = frozenset("cszvbgdr")

SYNONYMS = {
    "workforce": ("employee", "employ", "headcount", "staff", "people"),
    "employee": ("workforce", "employ", "headcount", "staff", "people"),
    "employ": ("workforce", "employee", "headcount", "staff"),
    "people": ("workforce", "employee", "employ"),
    "headcount": ("workforce", "employee", "employ"),
    "staff": ("workforce", "employee", "employ"),
    "revenue": ("turnover", "sales"),
    "turnover": ("revenue", "sales"),
    "sales": ("revenue", "turnover"),
    "profit": ("earning", "income"),
    "earning": ("profit", "income"),
    "income": ("profit", "earning"),
    "increase": ("grew", "growth", "expand", "rose", "higher"),
    "grew": ("increase", "growth", "expand"),
    "growth": ("increase", "expand", "grew"),
    "expand": ("increase", "growth", "grew"),
    "decrease": ("fell", "reduce", "decline", "lower"),
    "fell": ("decrease", "reduce", "decline"),
    "reduce": ("decrease", "fell", "decline"),
    "hire": ("recruit", "hired"),
    "hired": ("hire", "recruit"),
    "recruit": ("hire", "hired"),
}


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def stem_token(token: str) -> str:
    """Fold a few plural and past-tense forms so wording can overlap."""

    if len(token) >= 5 and token.endswith("ing"):
        base = token[:-3]
        if len(base) >= 3:
            token = base
    if len(token) >= 4 and token.endswith("ed"):
        base = token[:-2]
        if len(base) >= 3 and base[-1] in _E_RESTORE:
            token = base + "e"
        elif len(base) >= 3:
            token = base
    elif len(token) > 4 and token.endswith("s") and not token.endswith(("ss", "ness", "ous", "us", "is")):
        token = token[:-1]
    return token


def content_terms(text: str) -> set[str]:
    terms: set[str] = set()
    for token in tokenize(text):
        if token in STOPWORDS:
            continue
        if token.isdigit():
            terms.add(token)
            continue
        if len(token) < 2:
            continue
        base = stem_token(token)
        terms.add(base)
        for synonym in SYNONYMS.get(base, ()):
            terms.add(synonym)
    return terms


def term_coverage(query: str, text: str) -> float:
    query_terms = content_terms(query)
    if not query_terms:
        return 0.0
    return len(query_terms & content_terms(text)) / len(query_terms)


def normalize_ws(text: str) -> str:
    return " ".join(text.split())


def normalize_with_map(text: str) -> tuple[str, list[int]]:
    """Collapse whitespace and map each normalized character to an original index."""

    output: list[str] = []
    mapping: list[int] = []
    index = 0
    length = len(text)
    while index < length:
        if text[index].isspace():
            next_index = index + 1
            while next_index < length and text[next_index].isspace():
                next_index += 1
            if output and next_index < length:
                output.append(" ")
                mapping.append(index)
            index = next_index
            continue
        output.append(text[index])
        mapping.append(index)
        index += 1
    return "".join(output), mapping


def locate_quote(haystack: str, excerpt: str) -> str | None:
    """Return the exact source slice for an excerpt, ignoring whitespace runs.

    A match shorter than 8 characters is rejected so a single token cannot
    pass as a quotation.
    """

    needle = normalize_ws(excerpt)
    if len(needle) < 8:
        return None
    normalized, mapping = normalize_with_map(haystack)
    found = normalized.lower().find(needle.lower())
    if found < 0:
        return None
    start = mapping[found]
    end = mapping[found + len(needle) - 1] + 1
    return haystack[start:end]


def percentage_change(current: float, baseline: float) -> float | None:
    """Return the percent change from baseline to current.

    A non-positive baseline has no stable percent-change reading, so the
    caller must treat the claim as unverified rather than invent a figure.
    """

    if baseline <= 0:
        return None
    return (current - baseline) / baseline * 100.0


def format_percent(value: float) -> str:
    if abs(value - round(value)) < 0.05:
        return str(int(round(value)))
    return f"{value:.1f}"
