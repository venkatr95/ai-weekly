"""Audit an AI-generated answer against the sources that were supposed to support it."""

from answer_auditor.pipeline import audit, extract_claims
from answer_auditor.schemas import AuditReport

__all__ = ["AuditReport", "audit", "extract_claims"]
__version__ = "1.0.0"
