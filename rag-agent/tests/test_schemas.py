import pytest
from pydantic import ValidationError

from app.schemas.answer import Citation, QueryRequest, RAGResponse
from app.schemas.document import Document, DocumentChunk, DocumentUploadResponse


def test_document_and_chunk_schemas():
    document = Document(id="doc_123", filename="handbook.pdf", content_type="application/pdf")
    chunk = DocumentChunk(
        id="chunk_182",
        document_id="doc_123",
        text="Customers may request a refund within 30 days.",
        page=4,
        chunk_index=2,
    )
    uploaded = DocumentUploadResponse(document_id="doc_123", status="indexed", chunks=27)
    assert document.filename == "handbook.pdf"
    assert chunk.page == 4
    assert uploaded.chunks == 27


def test_query_rejects_an_empty_question():
    with pytest.raises(ValidationError):
        QueryRequest(question="")


def test_response_round_trip():
    response = RAGResponse(
        answer="Customers may request a refund within 30 days. [1]",
        citations=[Citation(id=1, document="refund-policy.pdf", page=4, chunk_id="chunk_123")],
    )
    restored = RAGResponse.model_validate(response.model_dump())
    assert restored.citations[0].chunk_id == "chunk_123"
    assert restored.model_dump(exclude_none=True)["citations"][0]["page"] == 4
