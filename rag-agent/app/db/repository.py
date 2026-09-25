"""Vector stores.

The memory store is the test double and the offline demo. PostgreSQL with
pgvector is the production store: document rows and embeddings live in one
database, and search uses cosine distance.
"""

import logging
import threading
import time
from dataclasses import dataclass

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base, DocumentRow, build_chunk_model
from app.schemas.answer import RetrievedChunk

logger = logging.getLogger("rag_agent.db")


@dataclass
class StoredDocument:
    id: str
    filename: str
    content_type: str
    status: str
    chunk_count: int


@dataclass
class StoredChunk:
    id: str
    document_id: str
    filename: str
    text: str
    page: int | None
    chunk_index: int
    embedding: list[float]


class InMemoryVectorStore:
    def __init__(self, dim: int) -> None:
        self.dim = dim
        self._documents: dict[str, StoredDocument] = {}
        self._chunks: list[StoredChunk] = []
        self._lock = threading.Lock()

    def add_document(self, document: StoredDocument, chunks: list[StoredChunk]) -> None:
        self._check_dim(chunks)
        with self._lock:
            self._documents[document.id] = document
            self._chunks.extend(chunks)

    def get_document(self, document_id: str) -> StoredDocument | None:
        with self._lock:
            return self._documents.get(document_id)

    def search(self, vector: list[float], top_k: int) -> list[RetrievedChunk]:
        with self._lock:
            chunks = list(self._chunks)
        scored: list[RetrievedChunk] = []
        for chunk in chunks:
            score = _cosine(vector, chunk.embedding)
            scored.append(_retrieved(chunk, score))
        scored.sort(key=lambda chunk: (-chunk.score, chunk.chunk_id))
        return scored[:top_k]

    def _check_dim(self, chunks: list[StoredChunk]) -> None:
        for chunk in chunks:
            if len(chunk.embedding) != self.dim:
                raise ValueError(
                    f"Embedding width {len(chunk.embedding)} does not match store width {self.dim}"
                )


class PostgresVectorStore:
    def __init__(self, database_url: str, dim: int) -> None:
        self.dim = dim
        self.Chunk = build_chunk_model(dim)
        self.engine = create_engine(database_url, pool_pre_ping=True)
        self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def ensure_schema(self) -> None:
        last_error: Exception | None = None
        for attempt in range(15):
            try:
                self._ensure_schema_once()
                return
            except RuntimeError:
                raise
            except Exception as exc:
                last_error = exc
                logger.warning("Database not ready (attempt %d/15): %s", attempt + 1, exc)
                time.sleep(1)
        raise RuntimeError("Could not initialize PostgreSQL") from last_error

    def add_document(self, document: StoredDocument, chunks: list[StoredChunk]) -> None:
        self._check_dim(chunks)
        with self._session() as session:
            session.add(
                DocumentRow(
                    id=document.id,
                    filename=document.filename,
                    content_type=document.content_type,
                    status=document.status,
                    created_at=_utcnow(),
                )
            )
            session.add_all(
                self.Chunk(
                    id=chunk.id,
                    document_id=chunk.document_id,
                    text=chunk.text,
                    page=chunk.page,
                    chunk_index=chunk.chunk_index,
                    embedding=chunk.embedding,
                )
                for chunk in chunks
            )
            session.commit()

    def get_document(self, document_id: str) -> StoredDocument | None:
        with self._session() as session:
            row = session.get(DocumentRow, document_id)
            if row is None:
                return None
            count = session.scalar(
                select(func.count())
                .select_from(self.Chunk)
                .where(self.Chunk.document_id == document_id)
            )
            return StoredDocument(
                id=row.id,
                filename=row.filename,
                content_type=row.content_type,
                status=row.status,
                chunk_count=int(count or 0),
            )

    def search(self, vector: list[float], top_k: int) -> list[RetrievedChunk]:
        distance = self.Chunk.embedding.cosine_distance(vector)
        statement = (
            select(
                self.Chunk.id,
                self.Chunk.document_id,
                self.Chunk.text,
                self.Chunk.page,
                self.Chunk.chunk_index,
                DocumentRow.filename,
                distance.label("distance"),
            )
            .join(DocumentRow, DocumentRow.id == self.Chunk.document_id)
            .order_by(distance, self.Chunk.id)
            .limit(top_k)
        )
        with self._session() as session:
            rows = session.execute(statement).all()
        found: list[RetrievedChunk] = []
        for row in rows:
            score = max(0.0, min(1.0, 1.0 - float(row.distance)))
            found.append(
                RetrievedChunk(
                    chunk_id=row.id,
                    document_id=row.document_id,
                    filename=row.filename,
                    page=row.page,
                    score=score,
                    vector_score=score,
                    text=row.text,
                )
            )
        return found

    def _ensure_schema_once(self) -> None:
        with self.engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            existing = _existing_vector_dim(connection)
            if existing is not None and existing != self.dim:
                raise RuntimeError(
                    f"chunks.embedding is vector({existing}) but this process embeds "
                    f"at width {self.dim}. Drop the database volume and start again."
                )
            Base.metadata.create_all(connection)
        try:
            with self.engine.begin() as connection:
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw "
                        "ON chunks USING hnsw (embedding vector_cosine_ops)"
                    )
                )
        except Exception:
            logger.warning("HNSW index was not created; search will scan the table", exc_info=True)

    def _check_dim(self, chunks: list[StoredChunk]) -> None:
        for chunk in chunks:
            if len(chunk.embedding) != self.dim:
                raise ValueError(
                    f"Embedding width {len(chunk.embedding)} does not match store width {self.dim}"
                )

    def _session(self) -> Session:
        return self._session_factory()


def _existing_vector_dim(connection) -> int | None:
    registered = connection.execute(text("SELECT to_regclass('public.chunks')")).scalar()
    if registered is None:
        return None
    formatted = connection.execute(
        text(
            """
            SELECT format_type(attribute.atttypid, attribute.atttypmod)
            FROM pg_attribute AS attribute
            WHERE attribute.attrelid = 'public.chunks'::regclass
              AND attribute.attname = 'embedding'
              AND NOT attribute.attisdropped
            """
        )
    ).scalar()
    if not formatted or "(" not in formatted:
        return None
    inside = formatted[formatted.find("(") + 1 : formatted.find(")")]
    return int(inside) if inside.isdigit() else None


def _retrieved(chunk: StoredChunk, score: float) -> RetrievedChunk:
    clamped = max(0.0, min(1.0, score))
    return RetrievedChunk(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        filename=chunk.filename,
        page=chunk.page,
        score=clamped,
        vector_score=clamped,
        text=chunk.text,
    )


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def _utcnow():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
