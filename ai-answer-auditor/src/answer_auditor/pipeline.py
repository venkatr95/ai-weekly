"""Run an audit from an answer and source documents through to a validated report."""

from __future__ import annotations

import logging
from pathlib import Path

from answer_auditor.claim_verifier import verify_claim
from answer_auditor.config import Settings, load_settings
from answer_auditor.document_loader import load_sources, read_answer
from answer_auditor.errors import InputError
from answer_auditor.evidence_retriever import retrieve_evidence
from answer_auditor.evidence_validator import validate_claim_evidence
from answer_auditor.providers import build_provider, reconcile
from answer_auditor.report_generator import build_summary, overall_assessment
from answer_auditor.schemas import (
    AuditReport,
    ClaimResult,
    ExtractedClaim,
    SourceDocument,
    SourceInfo,
)
from answer_auditor.security import scrub_text

logger = logging.getLogger("answer_auditor")


def extract_claims(answer: str, settings: Settings | None = None) -> list[ExtractedClaim]:
    if not answer or not answer.strip():
        raise InputError("The answer is empty.")
    active = settings or load_settings()
    provider = build_provider(active)
    claims, _warnings = provider.extract(answer, None)
    return claims


def audit(
    answer: str,
    sources: list[Path | str | dict],
    question: str | None = None,
    settings: Settings | None = None,
) -> AuditReport:
    if not answer or not answer.strip():
        raise InputError("The answer is empty.")
    active = settings or load_settings()
    documents, load_warnings = load_sources(sources)
    return audit_documents(answer, documents, question=question, settings=active, extra_warnings=load_warnings)


def audit_files(
    answer_path: Path,
    source_paths: list[Path],
    question: str | None = None,
    settings: Settings | None = None,
) -> AuditReport:
    return audit(read_answer(answer_path), source_paths, question=question, settings=settings)


def audit_documents(
    answer: str,
    documents: list[SourceDocument],
    question: str | None = None,
    settings: Settings | None = None,
    extra_warnings: list[str] | None = None,
    transport=None,
) -> AuditReport:
    active = settings or load_settings()
    provider = build_provider(active, transport)
    claims, extract_warnings = provider.extract(answer, question)
    logger.info("Loaded %s sources and extracted %s claims.", len(documents), len(claims))
    if active.log_source_text:
        for document in documents:
            logger.debug(
                "Source %s text: %s",
                document.source_id,
                scrub_text(document.full_text(), active.secrets),
            )
    evidence = {
        claim.claim_id: retrieve_evidence(claim.text, documents, k=active.retrieval_k) for claim in claims
    }
    model_verdicts = provider.verify(claims, evidence, question)
    results: list[ClaimResult] = []
    for claim, verdict in zip(claims, model_verdicts, strict=True):
        if provider.name != "heuristic":
            verdict = reconcile(verdict, verify_claim(claim, evidence.get(claim.claim_id, [])))
        status, explanation, supporting, contradicting, notes = validate_claim_evidence(
            claim,
            verdict.status,
            verdict.explanation,
            verdict.supporting,
            verdict.contradicting,
            verdict.notes,
            documents,
        )
        results.append(
            ClaimResult(
                claim_id=claim.claim_id,
                text=claim.text,
                claim_type=claim.claim_type,
                status=status,  # type: ignore[arg-type]
                explanation=explanation,
                supporting_evidence=supporting,
                contradicting_evidence=contradicting,
                verification_notes=notes,
                sentence_index=claim.sentence_index,
                paragraph_index=claim.paragraph_index,
                original_sentence=claim.original_sentence,
            )
        )
    summary = build_summary(results)
    report = AuditReport(
        question=question,
        overall_assessment=overall_assessment(summary),
        summary=summary,
        claims=results,
        sources=[_source_info(document) for document in documents],
        warnings=[*list(extra_warnings or []), *extract_warnings],
        provider=provider.name,
    )
    return scrub_report(report, active.secrets)


def scrub_report(report: AuditReport, secrets: list[str]) -> AuditReport:
    payload = _scrub_value(report.model_dump(mode="json"), secrets)
    return AuditReport.model_validate(payload)


def _scrub_value(value, secrets: list[str]):
    if isinstance(value, str):
        return scrub_text(value, secrets)
    if isinstance(value, list):
        return [_scrub_value(item, secrets) for item in value]
    if isinstance(value, dict):
        return {key: _scrub_value(item, secrets) for key, item in value.items()}
    return value


def _source_info(document: SourceDocument) -> SourceInfo:
    numbered = [page.page_number for page in document.pages if page.page_number is not None]
    return SourceInfo(
        source_id=document.source_id,
        title=document.title,
        path=document.path,
        file_type=document.file_type,
        page_count=max(numbered) if numbered else None,
    )
