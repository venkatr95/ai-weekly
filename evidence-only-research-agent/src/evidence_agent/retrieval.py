"""Rank indexed chunks. The score selects passages; it does not prove a claim."""

from __future__ import annotations

import numpy as np

from evidence_agent.embeddings import Embedder
from evidence_agent.schemas import RetrievedPassage
from evidence_agent.textutil import content_terms
from evidence_agent.vector_store import VectorStore


class Retriever:
    def __init__(self, store: VectorStore, embedder: Embedder) -> None:
        self.store = store
        self.embedder = embedder

    def retrieve(self, question: str, k: int, threshold: float) -> list[RetrievedPassage]:
        if not self.store.chunks or self.store.embeddings is None or self.store.embeddings.shape[0] == 0:
            return []
        query = np.asarray(self.embedder.embed_query(question), dtype=np.float32)
        if query.shape != (self.store.embeddings.shape[1],) or float(np.linalg.norm(query)) == 0.0:
            return []
        query = query / max(float(np.linalg.norm(query)), 1e-12)
        cosine = self.store.embeddings @ query
        query_terms = content_terms(question)
        ranked: list[RetrievedPassage] = []
        for index, chunk in enumerate(self.store.chunks):
            cosine_score = max(0.0, float(cosine[index]))
            chunk_terms = content_terms(chunk.text)
            lexical = (len(query_terms & chunk_terms) / len(query_terms)) if query_terms else 0.0
            score = 0.5 * cosine_score + 0.5 * lexical
            if score < threshold:
                continue
            ranked.append(
                RetrievedPassage(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    relative_path=chunk.relative_path,
                    text=chunk.text,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    score=score,
                    cosine=cosine_score,
                    lexical=lexical,
                )
            )
        ranked.sort(key=lambda passage: (-passage.score, passage.relative_path, passage.chunk_id))
        return ranked[:k]
