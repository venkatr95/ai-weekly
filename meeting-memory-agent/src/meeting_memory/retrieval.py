"""Keyword search reranked by a local hashed embedding.

The embedding is a hash of the same tokens used for linking. It reranks
keyword hits. It does not add a hit that shares no keywords, and it does not
call an external embedding service.
"""

from __future__ import annotations

import hashlib
import math

from meeting_memory.schemas import MemoryItem
from meeting_memory.textutil import related, tokens

_DIM = 64


def embed(text: str) -> list[float]:
    vector = [0.0] * _DIM
    found = tokens(text)
    if not found:
        return vector
    for token in found:
        digest = hashlib.sha1(token.encode("utf-8")).digest()
        bucket = digest[0] % _DIM
        sign = 1.0 if digest[1] % 2 == 0 else -1.0
        vector[bucket] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def hybrid_search(
    items: list[MemoryItem],
    query: str,
    *,
    kind: str | None = None,
    owner: str | None = None,
    status: str | None = None,
    limit: int = 8,
) -> list[MemoryItem]:
    required = set(tokens(query))
    query_vector = embed(query)
    owner_key = owner.casefold() if owner else None
    scored: list[tuple[float, str, MemoryItem]] = []
    for item in items:
        if kind and item.kind != kind:
            continue
        if status and item.status != status:
            continue
        if owner_key and (item.owner or "").casefold() != owner_key:
            continue
        keyword = bool(required) and related(required, set(item.topic_tokens))
        owner_named = bool(item.owner) and item.owner.casefold() in required
        if required and not keyword and not owner_named:
            continue
        if not required and owner_key is None:
            continue
        similarity = cosine(query_vector, embed(item.text))
        score = (2.0 if keyword else 0.0) + similarity
        scored.append((score, item.item_id, item))
    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [item for _, _, item in scored[:limit]]
