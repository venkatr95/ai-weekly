from __future__ import annotations

from pathlib import Path

from evidence_agent.textutil import decompose_question
from helpers import indexed_pipeline


def test_compound_question_splits_on_and() -> None:
    parts = decompose_question(
        "What evidence supports the effectiveness of Intervention X, and what long-term benefits are reported?"
    )
    assert len(parts) == 2
    assert "effectiveness" in parts[0]
    assert "long-term" in parts[1]


def test_unanswerable_question_abstains(tmp_path: Path) -> None:
    pipeline = indexed_pipeline(
        tmp_path,
        {
            "study.txt": (
                "The reported evidence supports the effectiveness of Intervention X. "
                "Intervention X produced a statistically significant improvement in sleep onset latency."
            )
        },
    )
    response, _passages = pipeline.ask("What effect did Intervention X have on blood pressure in children?")
    assert response.abstained is True
    assert response.claims == []
    assert response.unanswered_questions
    assert response.unanswered_questions[0].reason == "missing_documents"
    assert "blood pressure" not in response.answer.lower() or "do not contain" in response.answer.lower()


def test_partial_question_answers_only_the_supported_part(tmp_path: Path) -> None:
    pipeline = indexed_pipeline(
        tmp_path,
        {
            "study.txt": (
                "The reported evidence supports the effectiveness of Intervention X. "
                "A reported limitation is that follow-up lasted 6 weeks."
            )
        },
    )
    response, _passages = pipeline.ask(
        "What evidence supports the effectiveness of Intervention X, and what long-term benefits are reported?"
    )
    assert response.abstained is False
    assert any("effectiveness of Intervention X" in claim.text for claim in response.claims)
    assert any("long-term" in item.question for item in response.unanswered_questions)
    joined = " ".join(claim.text for claim in response.claims).lower()
    assert "long-term benefits are" not in joined
