"""Attach citations only when the claim is supported by a retrieved chunk.

A model (or the extractive fallback) may name a source number. This module
drops that number unless it was in the retrieval list, the claim overlaps the
question, the claim overlaps that chunk, and every digit in the claim appears
in one of the chunks it cites. If nothing survives, the answer is a refusal.
"""

import logging

from app.schemas.answer import INSUFFICIENT_ANSWER, Citation, ModelAnswer, RAGResponse, RetrievedChunk
from app.textutil import finish_sentence, min_hits_required, numbers_in, overlap_hits

logger = logging.getLogger("rag_agent.citations")


def insufficient_response() -> RAGResponse:
    return RAGResponse(answer=INSUFFICIENT_ANSWER, citations=[])


def build_response(question: str, sources: list[RetrievedChunk], model_answer: ModelAnswer) -> RAGResponse:
    if not model_answer.sufficient:
        logger.info("CITATION VALIDATION: model marked the question unsupported")
        return insufficient_response()

    by_id = {index: source for index, source in enumerate(sources, start=1)}
    required = min_hits_required(question)
    parts: list[str] = []
    used: list[int] = []
    used_set: set[int] = set()
    dropped = 0

    for claim in model_answer.claims:
        text = finish_sentence(claim.text)
        if not text:
            dropped += 1
            continue
        if overlap_hits(question, text) < required:
            dropped += 1
            continue
        valid_ids = _supported_ids(text, claim.citation_ids, by_id)
        if not valid_ids:
            dropped += 1
            continue
        markers = " ".join(f"[{citation_id}]" for citation_id in valid_ids)
        parts.append(f"{text} {markers}")
        for citation_id in valid_ids:
            if citation_id not in used_set:
                used_set.add(citation_id)
                used.append(citation_id)

    logger.info("CITATION VALIDATION: kept=%d dropped=%d", len(parts), dropped)
    if not parts:
        return insufficient_response()

    citations = [
        Citation(
            id=citation_id,
            document=by_id[citation_id].filename,
            page=by_id[citation_id].page,
            chunk_id=by_id[citation_id].chunk_id,
        )
        for citation_id in used
    ]
    return RAGResponse(answer=" ".join(parts), citations=citations)


def _supported_ids(claim: str, citation_ids: list[int], by_id: dict[int, RetrievedChunk]) -> list[int]:
    valid: list[int] = []
    seen: set[int] = set()
    for citation_id in citation_ids:
        if citation_id in seen or citation_id not in by_id:
            continue
        seen.add(citation_id)
        chunk = by_id[citation_id]
        if overlap_hits(claim, chunk.text) < 1:
            continue
        valid.append(citation_id)
    if not valid:
        return []
    combined = "\n".join(by_id[citation_id].text for citation_id in valid)
    if any(number not in combined for number in numbers_in(claim)):
        return []
    return valid
