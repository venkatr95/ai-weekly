"""SQLAlchemy models. The chunk embedding width is fixed when the store starts."""

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DocumentRow(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="indexed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


_chunk_models: dict[int, type[Any]] = {}


def build_chunk_model(dim: int) -> type[Any]:
    """Register the chunks table for this vector width. One width per process."""
    existing = _chunk_models.get(dim)
    if existing is not None:
        return existing

    class ChunkRow(Base):
        __tablename__ = "chunks"
        __table_args__ = {"extend_existing": True}

        id: Mapped[str] = mapped_column(String(64), primary_key=True)
        document_id: Mapped[str] = mapped_column(
            ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
        text: Mapped[str] = mapped_column(Text, nullable=False)
        page: Mapped[int | None] = mapped_column(Integer, nullable=True)
        chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
        embedding: Mapped[list[float]] = mapped_column(Vector(dim), nullable=False)

    _chunk_models[dim] = ChunkRow
    return ChunkRow
