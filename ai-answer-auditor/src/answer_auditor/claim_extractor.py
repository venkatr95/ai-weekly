"""Split an answer into atomic claims without adding statements that are not there."""

from __future__ import annotations

import re

from answer_auditor.schemas import ExtractedClaim
from answer_auditor.sentence_segmenter import Segment, segment_answer
from answer_auditor.textutil import content_terms

_SPLIT = re.compile(
    r";\s*|,\s+and\s+|\s+and\s+|,\s+but\s+|\s+but\s+",
    re.IGNORECASE,
)
_VERBS = (
    "achieved", "expanded", "hired", "generated", "increased", "decreased",
    "reported", "was", "were", "is", "are", "has", "have", "had", "grew",
    "fell", "announced", "opened", "closed", "employed", "recorded", "posted",
    "reached", "added", "reduced", "launched", "acquired", "sold", "paid",
    "earned", "lost", "raised", "lowered", "improved", "declined", "rose",
    "dropped", "cut", "signed", "approved", "rejected", "bought", "missed",
    "published", "remained", "became", "made", "showed", "delivered",
    "produced", "completed", "started", "ended", "recruited", "invested",
)
_VERB_START = re.compile(
    r"^(?:also\s+|then\s+|still\s+)?(?:" + "|".join(sorted(_VERBS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_SUBJECTS = (
    "the company", "the firm", "the group", "the business", "net profit",
    "revenue", "profit", "sales", "earnings", "workforce", "it", "they", "we",
)
_OPINION = re.compile(
    r"\b(i think|i believe|we believe|in my opinion|in our view|arguably|"
    r"it seems|it appears|perhaps|maybe|probably|excellent|impressive|"
    r"disappointing|successful year|strong year|great year|poor performance|"
    r"outstanding|terrible)\b",
    re.IGNORECASE,
)
_RECOMMEND = re.compile(
    r"\b(should|ought to|we recommend|i recommend|recommend that)\b",
    re.IGNORECASE,
)
_NON_FACTUAL = re.compile(
    r"^(thank you|thanks|hello|hi there|please find|the following|see below)\b",
    re.IGNORECASE,
)
_QUANTITY = re.compile(
    r"(?:€|\$|£|\bEUR\b|\bUSD\b|\bGBP\b)\s*\d|\d+(?:\.\d+)?\s*%|\b\d{1,3}(?:,\d{3})+\b|\b\d+(?:\.\d+)?\s*(?:million|billion|thousand)\b",
    re.IGNORECASE,
)
_HEDGE = re.compile(
    r"\b(may have|might have|could have|possibly|appears to)\b",
    re.IGNORECASE,
)


def extract_claims_heuristic(answer: str) -> list[ExtractedClaim]:
    claims: list[ExtractedClaim] = []
    for segment in segment_answer(answer):
        for piece in split_compound(segment.text):
            claims.append(
                ExtractedClaim(
                    claim_id=f"C{len(claims) + 1:03d}",
                    text=piece,
                    claim_type=classify_claim(piece),
                    sentence_index=segment.sentence_index,
                    paragraph_index=segment.paragraph_index,
                    original_sentence=segment.text,
                )
            )
    return claims


def classify_claim(text: str) -> str:
    if _NON_FACTUAL.search(text.strip()):
        return "non_factual"
    has_quantity = bool(_QUANTITY.search(text))
    if _RECOMMEND.search(text) and not has_quantity:
        return "recommendation"
    if _OPINION.search(text) and not has_quantity:
        return "opinion"
    if _HEDGE.search(text) and not has_quantity:
        return "factual"
    return "factual"


def split_compound(sentence: str) -> list[str]:
    """Split coordinated clauses. Keep the original sentence when a split would be unsafe."""

    stripped = sentence.strip()
    parts = [part.strip(" ,") for part in _SPLIT.split(stripped) if part.strip(" ,")]
    if len(parts) < 2:
        return [_ensure_period(stripped)]
    if any(len(part.split()) < 3 for part in parts):
        return [_ensure_period(stripped)]
    subject = _leading_subject(parts[0])
    rebuilt: list[str] = []
    for index, part in enumerate(parts):
        if index == 0:
            rebuilt.append(part)
            continue
        if _leading_subject(part):
            rebuilt.append(part)
            continue
        if _VERB_START.match(part):
            if subject is None:
                return [_ensure_period(stripped)]
            verb_part = re.sub(r"^(?:also\s+|then\s+|still\s+)", "", part, count=1, flags=re.IGNORECASE)
            rebuilt.append(f"{subject} {verb_part}")
            continue
        return [_ensure_period(stripped)]
    return [_ensure_period(part) for part in rebuilt]


def claim_is_in_answer(claim_text: str, answer: str) -> bool:
    """Reject a model claim that introduces facts the answer does not state."""

    if _normalize(claim_text) in _normalize(answer):
        return True
    claim_terms = content_terms(claim_text)
    answer_terms = content_terms(answer)
    if len(claim_terms) < 2:
        return False
    return claim_terms <= answer_terms


def segments_of(answer: str) -> list[Segment]:
    return segment_answer(answer)


def _leading_subject(text: str) -> str | None:
    lowered = text.lower()
    for subject in sorted(_SUBJECTS, key=len, reverse=True):
        if lowered.startswith(subject):
            return text[: len(subject)]
    return None


def _ensure_period(text: str) -> str:
    cleaned = " ".join(text.split())
    if not cleaned:
        return cleaned
    if cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    if cleaned[-1] not in ".!?":
        return cleaned + "."
    return cleaned


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())
