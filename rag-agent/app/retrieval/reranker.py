"""Blend vector similarity with term overlap.

The lexical score keeps exact policy phrases ("30 days", "parental leave")
ahead of a chunk that is only topically nearby. The vector score is what
search returned; the blended score is what generation and the refusal
threshold use.
"""

from app.schemas.answer import RetrievedChunk
from app.textutil import lexical_score


class Reranker:
    def __init__(self, vector_weight: float) -> None:
        if not 0 <= vector_weight <= 1:
            raise ValueError("vector_weight must be between 0 and 1")
        self.vector_weight = vector_weight

    def rerank(self, query: str, chunks: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        ranked: list[RetrievedChunk] = []
        lexical_weight = 1.0 - self.vector_weight
        for chunk in chunks:
            vector = chunk.vector_score if chunk.vector_score is not None else chunk.score
            vector = max(0.0, min(1.0, vector))
            blended = self.vector_weight * vector + lexical_weight * lexical_score(query, chunk.text)
            ranked.append(chunk.model_copy(update={"score": blended, "vector_score": vector}))
        ranked.sort(key=lambda chunk: (-chunk.score, chunk.chunk_id))
        return ranked[:top_k]
