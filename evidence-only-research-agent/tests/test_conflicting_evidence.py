from __future__ import annotations

from pathlib import Path

from evidence_agent.textutil import sentence_polarity
from helpers import indexed_pipeline


def test_polarity_detects_negation_and_ignores_hedged_limitations() -> None:
    assert sentence_polarity(
        "Intervention X produced a statistically significant improvement in sleep onset latency."
    ) == "positive"
    assert sentence_polarity(
        "Intervention X did not produce a statistically significant improvement in sleep onset latency."
    ) == "negative"
    assert (
        sentence_polarity(
            "The report says the sample is too small to establish effectiveness for Intervention X."
        )
        is None
    )


def test_conflict_is_presented_without_a_resolution(tmp_path: Path) -> None:
    pipeline = indexed_pipeline(
        tmp_path,
        {
            "study_a.txt": (
                "Intervention X produced a statistically significant improvement in sleep onset latency."
            ),
            "study_c.txt": (
                "Intervention X did not produce a statistically significant improvement in sleep onset latency."
            ),
        },
    )
    response, _passages = pipeline.ask(
        "Did Intervention X produce a statistically significant improvement in sleep onset latency?"
    )
    assert response.abstained is False
    assert response.conflicts
    assert response.conflicts[0].resolved is False
    sources = {citation.source_path for citation in response.citations}
    assert "study_a.txt" in sources
    assert "study_c.txt" in sources
    answer = response.answer.lower()
    assert "unresolved" in answer or "disagree" in answer
    assert "therefore" not in answer
