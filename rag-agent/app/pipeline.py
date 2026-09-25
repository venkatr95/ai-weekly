"""Ingest documents and answer questions.

Retrieval supplies the evidence, generation turns that evidence into claims,
and citation validation throws away any claim that does not point back at a
retrieved chunk.
"""

import logging
import uuid
from pathlib import Path

from app.citations.citation_builder import build_response, insufficient_response
from app.config import Settings
from app.db.repository import InMemoryVectorStore, PostgresVectorStore, StoredChunk, StoredDocument
from app.errors import DocumentNotFound, EmptyDocument
from app.generation.answer_generator import AnswerGenerator, assemble_context, build_generator
from app.ingestion.chunker import Chunker
from app.ingestion.embedder import Embedder, build_embedder
from app.ingestion.parser import parse_document
from app.retrieval.reranker import Reranker
from app.retrieval.retriever import Retriever
from app.schemas.answer import RAGResponse
from app.schemas.document import Document, DocumentUploadResponse
from app.textutil import normalize_question

logger = logging.getLogger("rag_agent.pipeline")


class RAGPipeline:
    def __init__(
        self,
        settings: Settings,
        embedder: Embedder,
        store: InMemoryVectorStore | PostgresVectorStore,
        chunker: Chunker,
        retriever: Retriever,
        generator: AnswerGenerator,
        min_score: float,
    ) -> None:
        self.settings = settings
        self.embedder = embedder
        self.store = store
        self.chunker = chunker
        self.retriever = retriever
        self.generator = generator
        self.min_score = min_score

    def ingest(self, filename: str, data: bytes, content_type: str) -> DocumentUploadResponse:
        safe_name = Path(filename).name
        pages = parse_document(safe_name, data, content_type)
        pieces = self.chunker.chunk(pages)
        if not pieces:
            raise EmptyDocument("Document contained no extractable text")
        vectors = self.embedder.embed_texts([piece.text for piece in pieces])
        document_id = _new_id("doc")
        stored = [
            StoredChunk(
                id=_new_id("chunk"),
                document_id=document_id,
                filename=safe_name,
                text=piece.text,
                page=piece.page,
                chunk_index=piece.chunk_index,
                embedding=vector,
            )
            for piece, vector in zip(pieces, vectors, strict=True)
        ]
        self.store.add_document(
            StoredDocument(
                id=document_id,
                filename=safe_name,
                content_type=content_type,
                status="indexed",
                chunk_count=len(stored),
            ),
            stored,
        )
        logger.info("INDEXED document=%s file=%s chunks=%d", document_id, safe_name, len(stored))
        return DocumentUploadResponse(document_id=document_id, status="indexed", chunks=len(stored))

    def get_document(self, document_id: str) -> Document:
        found = self.store.get_document(document_id)
        if found is None:
            raise DocumentNotFound(document_id)
        return Document(
            id=found.id,
            filename=found.filename,
            content_type=found.content_type,
            status=found.status,
            chunk_count=found.chunk_count,
        )

    def answer(self, question: str, top_k: int | None = None, debug: bool = False) -> RAGResponse:
        question = normalize_question(question)
        if not question:
            raise ValueError("Question is empty")
        k = top_k or self.settings.top_k
        logger.info("QUESTION: %s", question)
        ranked = self.retriever.retrieve(question, top_k=k)
        best = ranked[0].score if ranked else 0.0
        if not ranked or best < self.min_score:
            logger.info(
                "LLM: skipped (best score %.4f is below %.4f)",
                best,
                self.min_score,
            )
            response = insufficient_response()
            logger.info("ANSWER: %s", response.answer)
            logger.info("CITATIONS: []")
            return self._with_debug(response, ranked, debug)

        logger.info("CONTEXT:\n%s", assemble_context(ranked))
        logger.info("LLM: %s", self.generator.name)
        model_answer = self.generator.generate(question, ranked)
        response = build_response(question, ranked, model_answer)
        logger.info("ANSWER: %s", response.answer)
        if response.citations:
            for citation in response.citations:
                page = "n/a" if citation.page is None else str(citation.page)
                logger.info(
                    "CITATION [%d] %s page=%s %s",
                    citation.id,
                    citation.document,
                    page,
                    citation.chunk_id,
                )
        else:
            logger.info("CITATIONS: []")
        return self._with_debug(response, ranked, debug)

    def _with_debug(self, response: RAGResponse, ranked: list, debug: bool) -> RAGResponse:
        if not debug:
            return response
        return response.model_copy(update={"retrieved": ranked})


def build_pipeline(settings: Settings) -> RAGPipeline:
    embedder = build_embedder(settings)
    store = _build_store(settings, embedder.dim)
    weight = settings.vector_weight
    if weight is None:
        weight = 0.8 if embedder.name == "xai" else 0.45
    threshold = settings.min_score
    if threshold is None:
        threshold = 0.35 if embedder.name == "xai" else 0.18
    reranker = Reranker(weight)
    retriever = Retriever(
        embedder=embedder,
        store=store,
        reranker=reranker,
        pool_multiplier=settings.rerank_pool_multiplier,
    )
    return RAGPipeline(
        settings=settings,
        embedder=embedder,
        store=store,
        chunker=Chunker(settings.chunk_size_tokens, settings.chunk_overlap_tokens),
        retriever=retriever,
        generator=build_generator(settings),
        min_score=threshold,
    )


def _build_store(settings: Settings, dim: int) -> InMemoryVectorStore | PostgresVectorStore:
    if settings.vector_store == "memory":
        return InMemoryVectorStore(dim)
    store = PostgresVectorStore(settings.database_url, dim)
    store.ensure_schema()
    return store


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"
