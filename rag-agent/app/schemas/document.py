"""Document and chunk records carried through ingestion and the read API."""

from pydantic import BaseModel, Field


class Document(BaseModel):
    id: str
    filename: str
    content_type: str
    status: str = "indexed"
    chunk_count: int = 0


class DocumentChunk(BaseModel):
    id: str
    document_id: str
    text: str
    page: int | None = None
    chunk_index: int = Field(ge=0)


class DocumentUploadResponse(BaseModel):
    document_id: str
    status: str
    chunks: int = Field(ge=0)
