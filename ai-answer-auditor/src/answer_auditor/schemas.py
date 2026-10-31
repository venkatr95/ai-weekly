"""Pydantic records for claims, evidence, and the verification report."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

VerificationStatus = Literal[
    "supported",
    "partially_supported",
    "contradicted",
    "unsupported",
    "unverifiable",
]
ClaimType = Literal["factual", "opinion", "recommendation", "non_factual"]

STATUS_LABELS = {
    "supported": "Supported",
    "partially_supported": "Partially supported",
    "contradicted": "Contradicted",
    "unsupported": "Unsupported",
    "unverifiable": "Unverifiable",
}


class PageText(BaseModel):
    page_number: int | None = None
    text: str


class SourceDocument(BaseModel):
    source_id: str
    title: str | None = None
    path: str | None = None
    file_type: str
    pages: list[PageText] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def full_text(self) -> str:
        return "\n\n".join(page.text for page in self.pages if page.text.strip())


class SourceInfo(BaseModel):
    source_id: str
    title: str | None = None
    path: str | None = None
    file_type: str
    page_count: int | None = None


class EvidenceExcerpt(BaseModel):
    source_id: str
    quote: str
    page: int | None = None
    source_title: str | None = None


class ExtractedClaim(BaseModel):
    claim_id: str
    text: str
    claim_type: ClaimType
    sentence_index: int
    paragraph_index: int
    original_sentence: str


class ClaimResult(BaseModel):
    claim_id: str
    text: str
    claim_type: ClaimType
    status: VerificationStatus
    explanation: str
    supporting_evidence: list[EvidenceExcerpt] = Field(default_factory=list)
    contradicting_evidence: list[EvidenceExcerpt] = Field(default_factory=list)
    verification_notes: list[str] = Field(default_factory=list)
    sentence_index: int
    paragraph_index: int
    original_sentence: str


class Summary(BaseModel):
    total_claims: int
    supported: int
    partially_supported: int
    contradicted: int
    unsupported: int
    unverifiable: int
    factual_claims: int
    evidence_coverage: float | None = None


class AuditReport(BaseModel):
    question: str | None = None
    overall_assessment: str
    summary: Summary
    claims: list[ClaimResult]
    sources: list[SourceInfo] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provider: str

    @model_validator(mode="after")
    def check_counts(self) -> "AuditReport":
        summary = self.summary
        counted = (
            summary.supported
            + summary.partially_supported
            + summary.contradicted
            + summary.unsupported
            + summary.unverifiable
        )
        if counted != summary.total_claims:
            raise ValueError("Summary counts do not add up to total_claims.")
        if summary.total_claims != len(self.claims):
            raise ValueError("total_claims does not match the claims list.")
        factual = sum(1 for claim in self.claims if claim.claim_type == "factual")
        if factual != summary.factual_claims:
            raise ValueError("factual_claims does not match claim types.")
        status_counts = {status: 0 for status in STATUS_LABELS}
        for claim in self.claims:
            status_counts[claim.status] += 1
        if (
            status_counts["supported"] != summary.supported
            or status_counts["partially_supported"] != summary.partially_supported
            or status_counts["contradicted"] != summary.contradicted
            or status_counts["unsupported"] != summary.unsupported
            or status_counts["unverifiable"] != summary.unverifiable
        ):
            raise ValueError("Summary counts do not match claim statuses.")
        if factual == 0:
            if summary.evidence_coverage is not None:
                raise ValueError("evidence_coverage must be null when there are no factual claims.")
        else:
            expected = round(100.0 * summary.supported / factual, 1)
            if summary.evidence_coverage is None or abs(summary.evidence_coverage - expected) > 0.05:
                raise ValueError("evidence_coverage must be supported claims divided by factual claims.")
        return self


class Passage(BaseModel):
    source_id: str
    source_title: str | None = None
    page: int | None = None
    text: str
    context: str
    score: float


class AuditRequest(BaseModel):
    question: str | None = None
    answer: str
    sources: list[dict] = Field(default_factory=list)
