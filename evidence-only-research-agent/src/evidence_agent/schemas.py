"""Typed records for documents, retrieval, and evidence-grounded answers."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EvidenceStatus = Literal["supported", "interpretation", "unsupported"]
VerificationStatus = Literal["verified", "rejected", "unverified"]
UnansweredReason = Literal[
    "missing_documents",
    "insufficient_retrieval",
    "conflicting_evidence",
    "ambiguous_wording",
    "insufficient_evidence",
]


class PageSpan(BaseModel):
    start: int
    end: int
    page: int | None = None


class Chunk(BaseModel):
    chunk_id: str
    document_id: str
    relative_path: str
    text: str
    page_start: int | None = None
    page_end: int | None = None
    page_spans: list[PageSpan] = Field(default_factory=list)
    ordinal: int


class DocumentRecord(BaseModel):
    document_id: str
    relative_path: str
    file_type: str
    content_hash: str
    page_count: int | None = None
    needs_ocr: bool = False
    ocr_pages: list[int] = Field(default_factory=list)
    error: str | None = None
    warning: str | None = None
    chunk_ids: list[str] = Field(default_factory=list)
    char_count: int = 0


class PageText(BaseModel):
    page_number: int | None = None
    text: str
    needs_ocr: bool = False


class ExtractedDocument(BaseModel):
    absolute_path: str
    relative_path: str
    file_type: str
    content_hash: str
    pages: list[PageText] = Field(default_factory=list)
    needs_ocr: bool = False
    ocr_pages: list[int] = Field(default_factory=list)
    error: str | None = None
    warning: str | None = None

    @property
    def text(self) -> str:
        return "\n\n".join(page.text for page in self.pages if page.text.strip())


class RetrievedPassage(BaseModel):
    chunk_id: str
    document_id: str
    relative_path: str
    text: str
    page_start: int | None = None
    page_end: int | None = None
    score: float
    cosine: float
    lexical: float


class DraftCitation(BaseModel):
    chunk_id: str
    excerpt: str
    page: int | None = None


class DraftClaim(BaseModel):
    text: str
    evidence_status: EvidenceStatus = "supported"
    citations: list[DraftCitation] = Field(default_factory=list)


class DraftConflictPosition(BaseModel):
    summary: str
    citations: list[DraftCitation] = Field(default_factory=list)


class DraftConflict(BaseModel):
    topic: str
    positions: list[DraftConflictPosition] = Field(default_factory=list)
    resolved: bool = False
    note: str = "The documents do not resolve this conflict."


class DraftUnanswered(BaseModel):
    question: str
    reason: UnansweredReason
    detail: str
    citations: list[DraftCitation] = Field(default_factory=list)


class AnswerDraft(BaseModel):
    question: str
    answer: str
    claims: list[DraftClaim] = Field(default_factory=list)
    unanswered_questions: list[DraftUnanswered] = Field(default_factory=list)
    conflicts: list[DraftConflict] = Field(default_factory=list)
    abstained: bool = False
    limitations: list[str] = Field(default_factory=list)
    provider: str


class Citation(BaseModel):
    id: str
    chunk_id: str
    source_path: str
    page: int | None = None
    excerpt: str
    valid: bool
    supports_claim: bool
    rejection_reason: str | None = None


class Claim(BaseModel):
    id: str
    text: str
    evidence_status: EvidenceStatus
    citation_ids: list[str] = Field(default_factory=list)
    verification_status: VerificationStatus


class ConflictPosition(BaseModel):
    summary: str
    citation_ids: list[str] = Field(default_factory=list)


class Conflict(BaseModel):
    topic: str
    positions: list[ConflictPosition] = Field(default_factory=list)
    resolved: bool = False
    note: str


class UnansweredQuestion(BaseModel):
    question: str
    reason: UnansweredReason
    detail: str
    citation_ids: list[str] = Field(default_factory=list)


class AnswerResponse(BaseModel):
    question: str
    answer: str
    claims: list[Claim] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    unanswered_questions: list[UnansweredQuestion] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    abstained: bool
    limitations: list[str] = Field(default_factory=list)
    provider: str
    passages_retrieved: int = 0


class IndexStats(BaseModel):
    files_seen: int = 0
    files_indexed: int = 0
    files_reused: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    files_empty: int = 0
    files_needs_ocr: int = 0
    documents: int = 0
    chunks: int = 0


class IndexReport(BaseModel):
    index_dir: str
    stats: IndexStats
    errors: list[str] = Field(default_factory=list)
    ocr_warnings: list[str] = Field(default_factory=list)
    embedding_provider: str
    embedding_dimensions: int


class DiscoveredFile(BaseModel):
    absolute_path: str
    relative_path: str
    file_type: str
