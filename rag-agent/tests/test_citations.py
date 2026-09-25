from app.citations.citation_builder import build_response
from app.generation.answer_generator import SYSTEM_PROMPT
from app.schemas.answer import INSUFFICIENT_ANSWER, Claim, ModelAnswer, RetrievedChunk


def _source(text: str, page: int | None = 4) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="chunk_123",
        document_id="doc_42",
        filename="refund-policy.pdf",
        page=page,
        score=0.91,
        vector_score=0.88,
        text=text,
    )


def test_supported_claim_cites_the_retrieved_chunk():
    response = build_response(
        "What is the refund period?",
        [_source("The refund period is 30 days.")],
        ModelAnswer(
            sufficient=True,
            claims=[Claim(text="The refund period is 30 days.", citation_ids=[1])],
        ),
    )
    assert response.answer == "The refund period is 30 days. [1]"
    assert response.citations[0].id == 1
    assert response.citations[0].document == "refund-policy.pdf"
    assert response.citations[0].page == 4
    assert response.citations[0].chunk_id == "chunk_123"


def test_unknown_citation_id_is_removed():
    response = build_response(
        "What is the refund period?",
        [_source("The refund period is 30 days.")],
        ModelAnswer(
            sufficient=True,
            claims=[Claim(text="The refund period is 30 days.", citation_ids=[1, 9])],
        ),
    )
    assert "[9]" not in response.answer
    assert [citation.id for citation in response.citations] == [1]


def test_citation_that_was_never_retrieved_cannot_survive_alone():
    response = build_response(
        "What is the refund period?",
        [_source("The refund period is 30 days.")],
        ModelAnswer(
            sufficient=True,
            claims=[Claim(text="The refund period is 30 days.", citation_ids=[9])],
        ),
    )
    assert response.answer == INSUFFICIENT_ANSWER
    assert response.citations == []


def test_changed_number_is_not_supported():
    response = build_response(
        "What is the refund period?",
        [_source("The refund period is 30 days.")],
        ModelAnswer(
            sufficient=True,
            claims=[Claim(text="The refund period is 90 days.", citation_ids=[1])],
        ),
    )
    assert response.citations == []
    assert response.answer == INSUFFICIENT_ANSWER


def test_claim_about_a_different_question_is_dropped():
    response = build_response(
        "What is the company's annual revenue?",
        [_source("The refund period is 30 days.")],
        ModelAnswer(
            sufficient=True,
            claims=[Claim(text="The refund period is 30 days.", citation_ids=[1])],
        ),
    )
    assert response.answer == INSUFFICIENT_ANSWER
    assert response.citations == []


def test_model_can_refuse():
    response = build_response(
        "What is the refund period?",
        [_source("The refund period is 30 days.")],
        ModelAnswer(sufficient=False, claims=[]),
    )
    assert response.answer == INSUFFICIENT_ANSWER
    assert response.citations == []


def test_system_prompt_forbids_outside_knowledge():
    for rule in (
        "Do not use outside knowledge.",
        "Do not invent facts.",
        "Every factual claim must have a citation.",
        "If the sources do not contain enough information, say so.",
    ):
        assert rule in SYSTEM_PROMPT
