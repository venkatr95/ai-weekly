"""Embed a question, search the vector store, and rerank the candidates."""

import logging

from app.ingestion.embedder import Embedder
from app.retrieval.reranker import Reranker
from app.schemas.answer import RetrievedChunk

logger = logging.getLogger("rag_agent.retrieval")


class VectorStore:
    """Structural type implemented by the memory store and PostgreSQL."""

    dim: int

    def search(self, vector: list[float], top_k: int) -> list[RetrievedChunk]:
        raise NotImplementedError


class Retriever:
    def __init__(
        self,
        embedder: Embedder,
        store: VectorStore,
        reranker: Reranker,
        pool_multiplier: int,
    ) -> None:
        self.embedder = embedder
        self.store = store
        self.reranker = reranker
        self.pool_multiplier = pool_multiplier

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        vector = self.embedder.embed_query(query)
        logger.info(
            "QUERY EMBEDDING: %d dimensions via %s",
            len(vector),
            self.embedder.name,
        )
        pool = max(top_k, top_k * self.pool_multiplier)
        candidates = self.store.search(vector, top_k=pool)
        logger.info("VECTOR SEARCH: pool=%d candidates=%d", pool, len(candidates))
        ranked = self.reranker.rerank(query, candidates, top_k=top_k)
        logger.info("TOP %d CHUNKS:", len(ranked))
        for index, chunk in enumerate(ranked, start=1):
            preview = " ".join(chunk.text.split())[:160]
            logger.info(
                "  [%d] score=%.4f vector=%.4f %s page=%s %s :: %s",
                index,
                chunk.score,
                chunk.vector_score if chunk.vector_score is not None else chunk.score,
                chunk.filename,
                chunk.page if chunk.page is not None else "n/a",
                chunk.chunk_id,
                preview,
            )
        return ranked
