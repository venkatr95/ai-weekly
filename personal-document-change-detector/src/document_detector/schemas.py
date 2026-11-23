"""Pydantic records for documents, changes, and comparison reports."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

ChangeType = Literal["added", "removed", "modified", "moved", "unchanged", "formatting"]
Importance = Literal["critical", "high", "medium", "low", "informational"]
Category = Literal[
    "financial",
    "legal_contractual",
    "dates_deadlines",
    "responsibilities",
    "access_permissions",
    "policy",
    "operational",
    "numerical",
    "personnel",
    "general",
]

IMPORTANCE_LABELS = {
    "critical": "Critical",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "informational": "Informational",
}

CATEGORY_LABELS = {
    "financial": "Financial",
    "legal_contractual": "Legal or contractual wording",
    "dates_deadlines": "Dates and deadlines",
    "responsibilities": "Responsibilities",
    "access_permissions": "Access and permissions",
    "policy": "Policy changes",
    "operational": "Operational requirements",
    "numerical": "Numerical changes",
    "personnel": "Personnel or organizational",
    "general": "General textual changes",
}


class PageText(BaseModel):
    page_number: int | None = None
    text: str


class DocumentVersion(BaseModel):
    document_id: str
    filename: str
    path: str | None = None
    file_type: str
    pages: list[PageText] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def full_text(self) -> str:
        return "\n\n".join(page.text for page in self.pages if page.text.strip())


class NumericalDelta(BaseModel):
    kind: str
    previous_value: float | None = None
    updated_value: float | None = None
    unit: str | None = None
    currency: str | None = None
    absolute_difference: float | None = None
    percentage_difference: float | None = None
    direction: Literal["increased", "decreased", "unchanged", "unknown"] = "unknown"


class ChangeRecord(BaseModel):
    change_id: str
    change_type: ChangeType
    categories: list[Category] = Field(default_factory=list)
    importance: Importance
    importance_reason: str
    section: str | None = None
    previous_section: str | None = None
    updated_section: str | None = None
    title: str
    previous_text: str | None = None
    updated_text: str | None = None
    explanation: str
    impact: str
    recommendation: str
    previous_page: int | None = None
    updated_page: int | None = None
    previous_document_id: str
    updated_document_id: str
    numerical: NumericalDelta | None = None
    formatting_only: bool = False
    evidence_validated: bool = False


class ComparisonSummary(BaseModel):
    total_changes: int
    added: int
    removed: int
    modified: int
    moved: int
    formatting_only: int
    critical: int
    high: int
    medium: int
    low: int
    informational: int


class DocumentInfo(BaseModel):
    document_id: str
    filename: str
    path: str | None = None
    file_type: str
    page_count: int | None = None


class ComparisonReport(BaseModel):
    comparison_id: str
    documents: dict[str, DocumentInfo]
    summary: ComparisonSummary
    changes: list[ChangeRecord]
    review_recommendations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provider: str
    disclaimer: str = (
        "This report identifies textual differences and explains possible practical "
        "implications for human review. It is not legal, financial, or professional advice, "
        "and it does not determine whether a change is valid or enforceable."
    )

    @model_validator(mode="after")
    def check_counts(self) -> "ComparisonReport":
        summary = self.summary
        type_total = summary.added + summary.removed + summary.modified + summary.moved
        if type_total != summary.total_changes:
            raise ValueError("Change-type counts do not add up to total_changes.")
        if summary.total_changes != len(self.changes):
            raise ValueError("total_changes does not match the changes list.")
        importance_total = (
            summary.critical
            + summary.high
            + summary.medium
            + summary.low
            + summary.informational
        )
        if importance_total != summary.total_changes:
            raise ValueError("Importance counts do not add up to total_changes.")
        return self
