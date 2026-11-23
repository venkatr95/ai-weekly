"""End-to-end comparison pipeline."""

from __future__ import annotations

from pathlib import Path

from document_detector.config import Settings, importance_at_least, load_settings
from document_detector.document_aligner import align_sections
from document_detector.document_loader import load_pair
from document_detector.evidence_validator import validate_report_changes
from document_detector.providers import build_provider
from document_detector.report_generator import build_recommendations, build_summary
from document_detector.schemas import ComparisonReport, DocumentInfo, DocumentVersion
from document_detector.section_parser import parse_sections
from document_detector.text_diff import diff_aligned_sections
from document_detector.text_normalizer import normalize_document


def compare(
    old_path: str | Path,
    new_path: str | Path,
    *,
    settings: Settings | None = None,
    min_importance: str = "informational",
    include_formatting: bool = False,
    comparison_id: str = "comparison_001",
) -> ComparisonReport:
    """Compare two document versions and return a structured report."""

    settings = settings or load_settings()
    previous, updated = load_pair(Path(old_path), Path(new_path))
    return compare_documents(
        previous,
        updated,
        settings=settings,
        min_importance=min_importance,
        include_formatting=include_formatting,
        comparison_id=comparison_id,
    )


def compare_documents(
    previous: DocumentVersion,
    updated: DocumentVersion,
    *,
    settings: Settings | None = None,
    min_importance: str = "informational",
    include_formatting: bool = False,
    comparison_id: str = "comparison_001",
) -> ComparisonReport:
    settings = settings or load_settings()
    warnings = list(previous.warnings) + list(updated.warnings)

    norm_previous = normalize_document(previous)
    norm_updated = normalize_document(updated)

    prev_sections = parse_sections(norm_previous)
    upd_sections = parse_sections(norm_updated)
    aligned = align_sections(prev_sections, upd_sections)
    raw_changes = diff_aligned_sections(aligned)

    if not include_formatting:
        raw_changes = [change for change in raw_changes if not change.formatting_only]

    provider = build_provider(settings)
    changes = provider.explain(raw_changes, previous.document_id, updated.document_id)
    changes, evidence_warnings = validate_report_changes(changes, previous, updated)
    warnings.extend(evidence_warnings)

    changes = [
        change
        for change in changes
        if importance_at_least(change.importance, min_importance)
    ]

    summary = build_summary(changes)
    recommendations = build_recommendations(changes)
    return ComparisonReport(
        comparison_id=comparison_id,
        documents={
            "previous": _info(previous),
            "updated": _info(updated),
        },
        summary=summary,
        changes=changes,
        review_recommendations=recommendations,
        warnings=warnings,
        provider=provider.name,
    )


def _info(document: DocumentVersion) -> DocumentInfo:
    page_numbers = [page.page_number for page in document.pages if page.page_number is not None]
    page_count = len(document.pages) if document.file_type == "pdf" else (len(page_numbers) or None)
    return DocumentInfo(
        document_id=document.document_id,
        filename=document.filename,
        path=document.path,
        file_type=document.file_type,
        page_count=page_count,
    )
