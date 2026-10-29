"""Token, sentence, and excerpt helpers shared by indexing and verification."""

from __future__ import annotations

import re

STOPWORDS = frozenset(
    {
        "a", "an", "the", "of", "and", "or", "to", "in", "on", "for", "with",
        "by", "from", "that", "this", "these", "those", "is", "are", "was",
        "were", "be", "been", "being", "as", "at", "it", "its", "their", "his",
        "her", "they", "them", "what", "which", "how", "why", "who", "when",
        "where", "do", "does", "did", "across", "about", "into", "than", "then",
        "there", "have", "has", "had", "can", "could", "should", "would", "may",
        "might", "will", "shall", "also", "such", "using", "used", "use",
        "between", "among", "both", "each", "other", "any", "all", "some",
        "nor", "so", "if", "but", "we", "our", "you", "your", "he", "she",
        "per", "via", "within", "without", "over", "under", "after", "before",
        "during", "while", "because", "due", "only", "more", "most", "less",
        "least", "very", "just", "not", "no", "by", "many", "much",
    }
)

_TOKEN = re.compile(r"[\w]+", flags=re.UNICODE)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_E_RESTORE = frozenset("cszvbgdr")

MIN_SENTENCE_CHARS = 40


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def stem_token(token: str) -> str:
    """Light suffix stem so question wording and source wording can meet.

    This is not a linguistic stemmer. It only folds plural and past-tense
    forms that otherwise hide an exact lexical match.
    """

    if len(token) >= 4 and token.endswith("ing"):
        base = token[:-3]
        if len(base) >= 3:
            token = base
    if len(token) >= 4 and token.endswith("ed"):
        base = token[:-2]
        if len(base) >= 3 and base[-1] in _E_RESTORE:
            token = base + "e"
        elif len(base) >= 3:
            token = base
        elif len(base) == 2:
            token = base + "e"
    elif len(token) > 4 and token.endswith("s") and not token.endswith(("ss", "ness", "ous", "us", "is")):
        token = token[:-1]
    return token


def content_terms(text: str) -> set[str]:
    terms: set[str] = set()
    for token in tokenize(text):
        if token in STOPWORDS:
            continue
        if len(token) < 2 and not (token.isalpha() or token.isdigit()):
            continue
        if len(token) < 2 and token.isalpha():
            terms.add(token)
            continue
        if len(token) < 2:
            continue
        terms.add(stem_token(token))
    return terms


def feature_grams(text: str) -> list[str]:
    terms = [stem_token(token) for token in tokenize(text) if token not in STOPWORDS and len(token) >= 2]
    grams = list(terms)
    grams.extend(f"{left}_{right}" for left, right in zip(terms, terms[1:]))
    return grams


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


def find_excerpt_offsets(haystack: str, excerpt: str) -> list[int]:
    """Return original-text offsets where the excerpt occurs, ignoring whitespace runs."""

    needle = normalize_ws(excerpt)
    if len(needle) < 10:
        return []
    normalized, mapping = normalize_with_map(haystack)
    offsets: list[int] = []
    start = 0
    while True:
        found = normalized.find(needle, start)
        if found < 0:
            break
        offsets.append(mapping[found])
        start = found + max(1, len(needle))
    return offsets


def excerpt_in_text(excerpt: str, text: str) -> bool:
    return bool(find_excerpt_offsets(text, excerpt))


def split_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    for part in _SENTENCE_SPLIT.split(text):
        sentence = part.strip()
        if len(sentence) >= MIN_SENTENCE_CHARS:
            sentences.append(sentence)
    return sentences


def decompose_question(question: str) -> list[str]:
    """Split a compound question into subquestions without dropping the original wording."""

    pieces = re.split(
        r"\?\s+|;\s+|,\s*\band\b\s+(?=(?:what|which|how|why|whether|who|when|where|do|does|did|is|are|can|could)\b)|\s+\band\b\s+(?=(?:what|which|how|why|whether|who|when|where|do|does|did|is|are|can|could)\b)",
        question.strip(),
        flags=re.IGNORECASE,
    )
    subquestions: list[str] = []
    seen: set[str] = set()
    for piece in pieces:
        cleaned = piece.strip(" ?.!;")
        if len(cleaned.split()) < 3:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        subquestions.append(cleaned)
    if not subquestions:
        fallback = question.strip()
        if fallback:
            subquestions.append(fallback)
    return subquestions


def weighted_overlap(query_terms: set[str], sentence_terms: set[str], idf: dict[str, float]) -> float:
    if not query_terms:
        return 0.0
    numerator = 0.0
    denominator = 0.0
    for term in query_terms:
        weight = idf.get(term, 3.0)
        denominator += weight
        if term in sentence_terms:
            numerator += weight
    if denominator == 0:
        return 0.0
    return numerator / denominator


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


_NEGATION = re.compile(
    r"\b(did not|does not|do not|was not|were not|is not|are not|not produce|not improve|did not improve|no statistically|no significant|failed to)\b",
    re.IGNORECASE,
)
_POSITIVE = re.compile(
    r"\b(improvement|improve|improved|effective|effectiveness|benefit|benefits)\b",
    re.IGNORECASE,
)
_HEDGE = re.compile(
    r"\b(too small|preliminary|limitation|limited sample|cannot establish|could not establish|insufficient to)\b",
    re.IGNORECASE,
)
_CLEAR_NEGATION = re.compile(r"\bdid not\b|\bdoes not\b|\bno statistically\b", re.IGNORECASE)


def sentence_polarity(sentence: str) -> str | None:
    """Return positive, negative, or None for outcome-bearing sentences.

    Hedged limitation statements are not treated as a competing finding.
    """

    if not _POSITIVE.search(sentence):
        return None
    if _HEDGE.search(sentence) and not _CLEAR_NEGATION.search(sentence):
        return None
    if _NEGATION.search(sentence):
        return "negative"
    return "positive"


def definition_bonus(sentence: str) -> float:
    if re.search(r"\bis\b", sentence, flags=re.IGNORECASE) and re.search(
        r"\b(program|method|process|device|therapy|defined as|means)\b",
        sentence,
        flags=re.IGNORECASE,
    ):
        return 0.25
    return 0.0


def numbers_in(text: str) -> set[str]:
    return set(re.findall(r"\d+", text))


def shared_topic(left: set[str], right: set[str], limit: int = 6) -> str:
    shared = sorted(left & right)
    if not shared:
        return "overlapping claim"
    return ", ".join(shared[:limit])
