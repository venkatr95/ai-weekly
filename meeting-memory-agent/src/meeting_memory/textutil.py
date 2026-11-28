"""Token overlap used to link the same commitment across meetings.

Single generic verbs such as "own" or "use" are not enough to treat two
sentences as the same topic. A shared specific word, or two shared words, is.
"""

from __future__ import annotations

import re

STOP = {
    "a", "an", "the", "and", "or", "but", "if", "then", "so", "to", "of", "in",
    "on", "for", "from", "with", "by", "at", "as", "into", "over", "after",
    "before", "than", "that", "this", "these", "those", "it", "its", "we", "i",
    "you", "our", "your", "their", "they", "he", "she", "them", "me", "my",
    "be", "is", "are", "was", "were", "been", "being", "do", "does", "did",
    "will", "would", "can", "could", "should", "shall", "may", "might", "just",
    "also", "still", "about", "up", "out", "not", "no", "yes", "please",
    "someone", "somebody", "something", "probably", "everyone", "everybody",
    "have", "has", "had", "let", "lets", "going", "gonna", "today", "tomorrow",
    "tonight", "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday", "january", "february", "march", "april", "june",
    "july", "august", "september", "october", "november", "december", "jan",
    "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
}

# Stemmed forms. Question words that name the kind of answer, not the topic.
SCAFFOLD = {
    "previous", "meeting", "agree", "decide", "decision", "commitment", "commit",
    "change", "revise", "revised", "unresolved", "question", "remain", "ready",
    "expect", "make", "made", "any", "still", "own", "owner", "across", "about",
    "which", "what", "when", "where", "who", "team", "group", "folks",
    "task", "tasks", "belong", "assigned", "assign",
}

WEAK = {
    "own", "use", "write", "make", "update", "review", "take", "send", "complete",
    "finish", "agree", "decide", "remain", "keep", "stay", "need", "want",
    "look", "work", "move", "change", "open", "question", "done", "ship", "call",
    "meet", "talk", "say", "said", "mark", "leave",
}

_SYNONYMS = {
    "delivery": "deliver",
    "delivered": "deliver",
    "delivering": "deliver",
    "owns": "own",
    "owner": "own",
    "ownership": "own",
    "owned": "own",
    "decided": "decide",
    "decision": "decide",
    "decisions": "decide",
    "agreed": "agree",
    "agreement": "agree",
    "agreements": "agree",
    "notes": "note",
    "deployment": "deploy",
    "deployments": "deploy",
    "deployed": "deploy",
    "deploying": "deploy",
    "questions": "question",
    "reviews": "review",
    "reviewed": "review",
    "completed": "complete",
    "finished": "finish",
    "remains": "remain",
    "remaining": "remain",
    "expected": "expect",
    "changes": "change",
    "changed": "change",
    "commitments": "commitment",
    "committed": "commit",
    "meetings": "meeting",
    "revised": "revise",
}


def stem(word: str) -> str:
    """Map known variants. Do not strip a trailing s from arbitrary words.

    "previous" and "postgres" both end in s and are not plurals.
    """

    return _SYNONYMS.get(word, word)


def tokens(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for raw in re.findall(r"[0-9A-Za-z]+", text.lower()):
        if raw in STOP or raw.isdigit() or len(raw) < 2:
            continue
        token = stem(raw)
        if token in STOP or token in seen:
            continue
        seen.add(token)
        found.append(token)
    return sorted(found)


def required_tokens(question: str) -> list[str]:
    return [token for token in tokens(question) if token not in SCAFFOLD]


def related(left: set[str], right: set[str]) -> bool:
    shared = left & right
    if not shared:
        return False
    if len(shared) >= 2:
        return True
    token = next(iter(shared))
    if token in WEAK:
        return False
    if len(token) >= 5:
        return True
    smaller = min(len(left), len(right))
    return smaller == 1 and len(token) >= 3


def overlap_count(left: set[str], right: set[str]) -> int:
    return len(left & right)
