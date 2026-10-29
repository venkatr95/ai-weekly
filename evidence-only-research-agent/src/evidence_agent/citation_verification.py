"""Check that every citation points at a real passage and that the passage supports the claim."""

from __future__ import annotations

from evidence_agent.config import Settings
from evidence_agent.schemas import (
    AnswerDraft,
    AnswerResponse,
    Chunk,
    Citation,
    Claim,
    Conflict,
    ConflictPosition,
    DraftCitation,
    UnansweredQuestion,
)
from evidence_agent.textutil import content_terms, excerpt_in_text, find_excerpt_offsets, normalize_ws, numbers_in

_REMOTE_DETAILS = {
    "missing_documents": "The retrieved passages do not contain the information requested.",
    "insufficient_retrieval": "No passage scored above the retrieval threshold.",
    "conflicting_evidence": "The retrieved passages disagree.",
    "ambiguous_wording": "The question is too ambiguous to match a passage.",
    "insufficient_evidence": "The retrieved passages do not support an answer.",
}


def pages_for_excerpt(chunk: Chunk, excerpt: str) -> set[int | None]:
    offsets = find_excerpt_offsets(chunk.text, excerpt)
    if not offsets:
        return set()
    pages: set[int | None] = set()
    for offset in offsets:
        matched = False
        for span in chunk.page_spans:
            if span.start <= offset < span.end:
                pages.add(span.page)
                matched = True
        if not matched:
            pages.add(chunk.page_start)
    return pages


def excerpt_page(chunk: Chunk, excerpt: str) -> int | None:
    numeric = sorted(page for page in pages_for_excerpt(chunk, excerpt) if isinstance(page, int))
    if numeric:
        return numeric[0]
    return None


def assess_citation(
    chunk: Chunk | None,
    citation: DraftCitation,
    claim_text: str,
    evidence_status: str,
    support_threshold: float,
) -> tuple[bool, bool, str | None]:
    """Return valid, supports_claim, rejection_reason.

    Validity means the excerpt is a real span of an indexed chunk with matching
    page metadata. Support is a separate lexical check. A high retrieval score
    is intentionally not an input.
    """

    if chunk is None:
        return False, False, "unknown chunk id"
    if len(normalize_ws(citation.excerpt)) < 10:
        return False, False, "excerpt is empty or too short"
    if not excerpt_in_text(citation.excerpt, chunk.text):
        return False, False, "excerpt is not in the indexed chunk"
    pages = pages_for_excerpt(chunk, citation.excerpt)
    numeric_pages = {page for page in pages if isinstance(page, int)}
    if numeric_pages:
        if citation.page not in numeric_pages:
            return False, False, "page does not match the excerpt"
    elif citation.page is not None:
        return False, False, "source has no page number"
    if not _supports(claim_text, citation.excerpt, evidence_status, support_threshold):
        return True, False, "excerpt does not support the claim"
    return True, True, None


def _supports(claim_text: str, excerpt: str, evidence_status: str, support_threshold: float) -> bool:
    if evidence_status == "unsupported":
        return False
    claim_numbers = numbers_in(claim_text)
    if not claim_numbers <= numbers_in(excerpt):
        return False
    claim_terms = content_terms(claim_text)
    if not claim_terms:
        return False
    coverage = len(claim_terms & content_terms(excerpt)) / len(claim_terms)
    required = support_threshold if evidence_status == "supported" else min(0.35, support_threshold)
    return coverage >= required


class VerificationOutcome:
    def __init__(self, response: AnswerResponse, input_claims: int, dropped_claims: int) -> None:
        self.response = response
        self.input_claims = input_claims
        self.dropped_claims = dropped_claims


def verify_answer(
    draft: AnswerDraft,
    chunks_by_id: dict[str, Chunk],
    settings: Settings,
    passages_retrieved: int = 0,
) -> VerificationOutcome:
    citations: list[Citation] = []
    kept_claims: list[Claim] = []
    dropped = 0

    def take(draft_citation: DraftCitation, claim_text: str, evidence_status: str) -> str | None:
        chunk = chunks_by_id.get(draft_citation.chunk_id)
        valid, supports, reason = assess_citation(
            chunk,
            draft_citation,
            claim_text,
            evidence_status,
            settings.support_threshold,
        )
        if not valid or not supports:
            return None
        citation_id = f"cit-{len(citations) + 1}"
        citations.append(
            Citation(
                id=citation_id,
                chunk_id=draft_citation.chunk_id,
                source_path=chunk.relative_path if chunk else "",
                page=draft_citation.page,
                excerpt=normalize_ws(draft_citation.excerpt),
                valid=True,
                supports_claim=True,
                rejection_reason=None,
            )
        )
        return citation_id

    for draft_claim in draft.claims:
        if not draft_claim.text.strip():
            dropped += 1
            continue
        citation_ids = [
            citation_id
            for citation in draft_claim.citations
            if (citation_id := take(citation, draft_claim.text, draft_claim.evidence_status))
        ]
        if not citation_ids:
            dropped += 1
            continue
        kept_claims.append(
            Claim(
                id=f"claim-{len(kept_claims) + 1}",
                text=draft_claim.text.strip(),
                evidence_status=draft_claim.evidence_status,
                citation_ids=citation_ids,
                verification_status="verified",
            )
        )

    conflicts: list[Conflict] = []
    for draft_conflict in draft.conflicts:
        positions: list[ConflictPosition] = []
        for position in draft_conflict.positions:
            citation_ids = [
                citation_id
                for citation in position.citations
                if (citation_id := take(citation, position.summary, "supported"))
            ]
            if citation_ids:
                positions.append(ConflictPosition(summary=position.summary.strip(), citation_ids=citation_ids))
        if len(positions) < 2:
            continue
        conflicts.append(
            Conflict(
                topic=draft_conflict.topic,
                positions=positions,
                resolved=False,
                note="The documents do not resolve this conflict.",
            )
        )

    unanswered: list[UnansweredQuestion] = []
    for item in draft.unanswered_questions:
        valid_ids: list[str] = []
        excerpts: list[str] = []
        for citation in item.citations:
            citation_id = take(citation, citation.excerpt, "supported")
            if citation_id:
                valid_ids.append(citation_id)
                excerpts.append(normalize_ws(citation.excerpt))
        if draft.provider == "extractive":
            detail = item.detail
        else:
            detail = _REMOTE_DETAILS.get(item.reason, "The available passages do not answer this part.")
            if excerpts:
                detail = f"{detail} Passage: {excerpts[0]}"
        unanswered.append(
            UnansweredQuestion(
                question=item.question.strip(),
                reason=item.reason,
                detail=detail,
                citation_ids=valid_ids,
            )
        )

    abstained = not kept_claims and not conflicts
    limitations = _limitations(draft.provider, abstained, bool(unanswered), dropped, conflicts)
    response = AnswerResponse(
        question=draft.question,
        answer=_compose_answer(kept_claims, unanswered, conflicts, abstained),
        claims=kept_claims,
        citations=citations,
        unanswered_questions=unanswered,
        conflicts=conflicts,
        abstained=abstained,
        limitations=limitations,
        provider=draft.provider,
        passages_retrieved=passages_retrieved,
    )
    return VerificationOutcome(response, len(draft.claims), dropped)


def _compose_answer(claims: list[Claim], unanswered: list[UnansweredQuestion], conflicts: list[Conflict], abstained: bool) -> str:
    if abstained and not claims and not conflicts:
        return (
            "The indexed documents do not contain sufficient evidence to answer this question. "
            "No conclusion should be inferred from that gap."
        )
    parts: list[str] = []
    if conflicts:
        parts.append(
            "The retrieved sources disagree. Each position is cited separately, and the conflict is unresolved."
        )
    if claims:
        noun = "statement" if len(claims) == 1 else "statements"
        parts.append(f"The documents support {len(claims)} cited {noun}.")
    if unanswered:
        parts.append("Some parts of the question remain unanswered by the available evidence.")
    return " ".join(parts) if parts else (
        "The indexed documents do not contain sufficient evidence to answer this question."
    )


def _limitations(provider: str, abstained: bool, has_unanswered: bool, dropped: int, conflicts: list[Conflict]) -> list[str]:
    notes = [
        "Supported statements are limited to passages retrieved from the indexed documents.",
        "A retrieval score is not treated as proof. Each finding was checked against the stored source text.",
    ]
    if conflicts:
        notes.append("Version 1 does not choose between conflicting sources, even if another passage comments on both.")
    if has_unanswered and not abstained:
        notes.append(
            "The indexed documents do not contain sufficient evidence to resolve the unanswered questions. "
            "No conclusion should be inferred from their absence."
        )
    if abstained:
        notes.append(
            "The indexed documents do not contain sufficient evidence to answer this question. "
            "No conclusion should be inferred from that gap."
        )
    if dropped:
        notes.append(
            f"{dropped} generated claims were removed because their citations were invalid or did not support the wording."
        )
    if provider == "extractive":
        notes.append(
            "The extractive provider quotes source sentences. It does not paraphrase and it does not add outside knowledge."
        )
    else:
        notes.append(
            f"Claim wording was requested from the {provider} provider. "
            "Retrieved passages were sent to that provider. Unverified prose was not copied into the answer."
        )
    return notes
