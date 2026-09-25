"""Token overlap used by retrieval, the extractive answerer, and citation checks.

Embeddings use the surface terms. Evidence checks use a 5-character stem so
"processed" still supports a claim that says "process", without a stemmer package.
"""

import re

_WORD = re.compile(r"[a-z0-9]+")
_NUMBER = re.compile(r"\d+")
_WHITESPACE = re.compile(r"\s+")
_MARKER = re.compile(r"\s*\[\d+\]")

STOPWORDS = frozenset(
    {
        "a", "an", "the", "is", "are", "of", "to", "and", "or", "for", "in", "on",
        "with", "within", "that", "this", "be", "as", "by", "from", "at", "it",
        "its", "their", "our", "your", "may", "can", "do", "does", "did", "how",
        "what", "when", "where", "who", "which", "why", "long", "have", "has",
        "had", "before", "after", "into", "about", "between", "than", "then",
        "once", "also", "will", "would", "should", "could", "such", "if", "any",
        "all", "per", "via", "not", "no", "nor", "but", "so", "just", "only",
        "over", "under", "again", "each", "other", "these", "those", "them",
        "they", "was", "were", "been", "being", "am", "during", "without",
        "through", "until", "while", "because", "both", "few", "more", "most",
        "some", "same", "own", "too", "very", "many", "much", "someone", "take",
        "takes", "taken", "using", "used", "into", "out", "up", "down",
    }
)

# Terms that show up in almost every policy sentence and should not count as evidence.
WEAK_TERMS = frozenset(
    {
        "policy",
        "policies",
        "section",
        "document",
        "information",
        "please",
        "support",
        "employee",
        "employees",
        "customer",
        "customers",
    }
)


def normalize_question(question: str) -> str:
    return _WHITESPACE.sub(" ", question).strip()


def content_terms(text: str) -> list[str]:
    terms: list[str] = []
    for raw in _WORD.findall(text.lower()):
        if raw in STOPWORDS:
            continue
        if raw.isdigit() or len(raw) >= 3:
            terms.append(raw)
    return terms


def stem_key(term: str) -> str:
    return term[:5] if len(term) >= 5 else term


def significant_terms(text: str) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    for term in content_terms(text):
        if term in WEAK_TERMS:
            continue
        key = stem_key(term)
        if key in seen:
            continue
        seen.add(key)
        terms.append(term)
    return terms


def term_matches(query_term: str, document_terms: set[str]) -> bool:
    key = stem_key(query_term)
    return any(stem_key(other) == key for other in document_terms)


def overlap_hits(query: str, text: str) -> int:
    needed = significant_terms(query)
    if not needed:
        return 0
    found = set(content_terms(text))
    return sum(1 for term in needed if term_matches(term, found))


def min_hits_required(query: str) -> int:
    """Short questions must match every term. Longer ones need two, so one shared word is not enough."""
    count = len(significant_terms(query))
    if count <= 2:
        return count
    return 2


def lexical_score(query: str, text: str) -> float:
    total = len(significant_terms(query))
    if total == 0:
        return 0.0
    return overlap_hits(query, text) / total


def numbers_in(text: str) -> list[str]:
    return _NUMBER.findall(text)


def finish_sentence(text: str) -> str:
    cleaned = _MARKER.sub("", text)
    cleaned = _WHITESPACE.sub(" ", cleaned).strip()
    if not cleaned:
        return ""
    if cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned
