from __future__ import annotations

from evidence_agent.citation_verification import assess_citation, verify_answer
from evidence_agent.config import Settings
from evidence_agent.schemas import AnswerDraft, Chunk, DraftCitation, DraftClaim, PageSpan


def _settings() -> Settings:
    return Settings(index_dir="data/index")


def _chunk() -> Chunk:
    text = "The office rent is 4200 dollars per month for the downtown lease."
    return Chunk(
        chunk_id="chunk-rent",
        document_id="doc-rent",
        relative_path="budget_notes.md",
        text=text,
        page_start=None,
        page_end=None,
        page_spans=[PageSpan(start=0, end=len(text), page=None)],
        ordinal=0,
    )


def test_verbatim_excerpt_supports_the_same_sentence() -> None:
    chunk = _chunk()
    valid, supports, reason = assess_citation(
        chunk,
        DraftCitation(chunk_id=chunk.chunk_id, excerpt=chunk.text, page=None),
        chunk.text,
        "supported",
        0.55,
    )
    assert valid and supports and reason is None


def test_similarity_is_not_enough_when_the_excerpt_does_not_support_the_claim() -> None:
    chunk = _chunk()
    valid, supports, reason = assess_citation(
        chunk,
        DraftCitation(chunk_id=chunk.chunk_id, excerpt=chunk.text, page=None),
        "Children's blood pressure fell by 50 percent in the trial.",
        "supported",
        0.55,
    )
    assert valid is True
    assert supports is False
    assert reason == "excerpt does not support the claim"


def test_rejects_unknown_chunk_wrong_page_and_changed_excerpt() -> None:
    text = "In Rivera 2024 the primary outcome improved by 18 minutes."
    chunk = Chunk(
        chunk_id="chunk-a",
        document_id="doc-a",
        relative_path="study_a.pdf",
        text=text,
        page_start=2,
        page_end=2,
        page_spans=[PageSpan(start=0, end=len(text), page=2)],
        ordinal=0,
    )
    unknown, _, unknown_reason = assess_citation(
        None,
        DraftCitation(chunk_id="missing", excerpt=text, page=2),
        text,
        "supported",
        0.55,
    )
    assert unknown is False
    assert unknown_reason == "unknown chunk id"

    wrong_page, _, page_reason = assess_citation(
        chunk,
        DraftCitation(chunk_id=chunk.chunk_id, excerpt=text, page=9),
        text,
        "supported",
        0.55,
    )
    assert wrong_page is False
    assert page_reason == "page does not match the excerpt"

    changed, _, changed_reason = assess_citation(
        chunk,
        DraftCitation(chunk_id=chunk.chunk_id, excerpt=text.replace("18", "40"), page=2),
        text.replace("18", "40"),
        "supported",
        0.55,
    )
    assert changed is False
    assert changed_reason == "excerpt is not in the indexed chunk"


def test_failed_validation_abstains_instead_of_keeping_the_claim() -> None:
    chunk = _chunk()
    draft = AnswerDraft(
        question="What is the office rent?",
        answer="The model invented a second fact.",
        provider="extractive",
        claims=[
            DraftClaim(
                text="The office rent is 9999 dollars per month.",
                citations=[DraftCitation(chunk_id=chunk.chunk_id, excerpt="The office rent is 9999 dollars per month.", page=None)],
            )
        ],
    )
    outcome = verify_answer(draft, {chunk.chunk_id: chunk}, _settings())
    assert outcome.response.abstained is True
    assert outcome.response.claims == []
    assert "9999" not in outcome.response.answer
    assert outcome.dropped_claims == 1
