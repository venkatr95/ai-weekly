"""Query, generation, and citation models.

`RetrievedChunk` is the record generation is allowed to cite. A citation that
does not point at one of these chunks is dropped before the response is returned.
"""

from pydantic import BaseModel, Field, model_serializer


INSUFFICIENT_ANSWER = (
    "I couldn't find sufficient information in the provided documents to answer this question."
)


class Citation(BaseModel):
    id: int = Field(ge=1)
    document: str
    page: int | None = None
    chunk_id: str


class RetrievedChunk(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    page: int | None = None
    score: float
    vector_score: float | None = None
    text: str


class Claim(BaseModel):
    text: str
    citation_ids: list[int] = Field(default_factory=list)


class ModelAnswer(BaseModel):
    """Structured answer the language model must return. Markers are added later."""

    sufficient: bool
    claims: list[Claim] = Field(default_factory=list)


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    debug: bool = False


class RAGResponse(BaseModel):
    answer: str
    citations: list[Citation]
    retrieved: list[RetrievedChunk] | None = None

    @model_serializer(mode="wrap")
    def _hide_debug_field(self, handler):
        payload = handler(self)
        if payload.get("retrieved") is None:
            payload.pop("retrieved", None)
        return payload
