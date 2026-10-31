"""Keep only quotations that occur in the extracted source text."""

from __future__ import annotations

from answer_auditor.schemas import ClaimResult, EvidenceExcerpt, ExtractedClaim, SourceDocument
from answer_auditor.textutil import locate_quote


def validate_claim_evidence(
    claim: ExtractedClaim,
    status: str,
    explanation: str,
    supporting: list[EvidenceExcerpt],
    contradicting: list[EvidenceExcerpt],
    notes: list[str],
    documents: list[SourceDocument],
) -> tuple[str, str, list[EvidenceExcerpt], list[EvidenceExcerpt], list[str]]:
    """Drop invented quotations. Downgrade a status that no longer has its evidence."""

    by_id = {document.source_id: document for document in documents}
    notes = list(notes)
    valid_supporting, dropped_support = _filter_quotes(supporting, by_id, notes)
    valid_contradicting, dropped_conflict = _filter_quotes(contradicting, by_id, notes)
    if status == "supported" and not valid_supporting:
        status = "unsupported"
        explanation = (
            "The proposed support was discarded because the quotation is not in the source text. "
            "Missing evidence is not a contradiction."
        )
        notes.append("A supporting quotation was not found in the extracted source text.")
    elif status == "contradicted" and not valid_contradicting:
        status = "unsupported"
        explanation = (
            "The proposed contradiction was discarded because the quotation is not in the source text. "
            "Missing evidence is not a contradiction."
        )
        notes.append("A contradicting quotation was not found in the extracted source text.")
    elif status == "partially_supported" and not valid_supporting and not valid_contradicting:
        status = "unsupported"
        explanation = (
            "The proposed evidence was discarded because the quotation is not in the source text."
        )
    del dropped_support, dropped_conflict, claim
    return status, explanation, valid_supporting, valid_contradicting, _unique(notes)


def quote_is_in_source(excerpt: EvidenceExcerpt, documents: list[SourceDocument]) -> bool:
    document = next((item for item in documents if item.source_id == excerpt.source_id), None)
    if document is None:
        return False
    return locate_quote(document.full_text(), excerpt.quote) is not None


def _filter_quotes(
    excerpts: list[EvidenceExcerpt],
    documents: dict[str, SourceDocument],
    notes: list[str],
) -> tuple[list[EvidenceExcerpt], int]:
    kept: list[EvidenceExcerpt] = []
    dropped = 0
    for excerpt in excerpts:
        document = documents.get(excerpt.source_id)
        if document is None:
            dropped += 1
            notes.append(f"Dropped a quotation for unknown source {excerpt.source_id}.")
            continue
        exact = locate_quote(document.full_text(), excerpt.quote)
        if exact is None:
            dropped += 1
            notes.append(
                f"Dropped a quotation that does not appear in {excerpt.source_id}."
            )
            continue
        kept.append(excerpt.model_copy(update={"quote": exact.strip(), "source_title": excerpt.source_title or document.title}))
    return kept, dropped


def _unique(notes: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for note in notes:
        if note not in seen:
            seen.add(note)
            unique.append(note)
    return unique


def validate_result(result: ClaimResult, documents: list[SourceDocument]) -> ClaimResult:
    status, explanation, supporting, contradicting, notes = validate_claim_evidence(
        ExtractedClaim(
            claim_id=result.claim_id,
            text=result.text,
            claim_type=result.claim_type,
            sentence_index=result.sentence_index,
            paragraph_index=result.paragraph_index,
            original_sentence=result.original_sentence,
        ),
        result.status,
        result.explanation,
        result.supporting_evidence,
        result.contradicting_evidence,
        result.verification_notes,
        documents,
    )
    return result.model_copy(
        update={
            "status": status,
            "explanation": explanation,
            "supporting_evidence": supporting,
            "contradicting_evidence": contradicting,
            "verification_notes": notes,
        }
    )
