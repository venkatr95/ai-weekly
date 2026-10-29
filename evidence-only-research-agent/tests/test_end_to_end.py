from __future__ import annotations

import json
from pathlib import Path

from evidence_agent.evaluation import evaluate, load_questions
from evidence_agent.schemas import AnswerResponse
from helpers import build_settings
from evidence_agent.pipeline import ResearchPipeline

import cli


ROOT = Path(__file__).resolve().parents[1]


def test_gold_questions_meet_evidence_checks(example_documents: Path, tmp_path: Path) -> None:
    questions = load_questions(ROOT / "examples" / "questions.json")
    pipeline = ResearchPipeline(build_settings(tmp_path))
    report = evaluate(pipeline, example_documents, questions)
    failures = [
        f"{result.id}: recall={result.recall_hit} phrases={result.phrases_hit} "
        f"abstained={result.abstained} conflict={result.conflict_detected} "
        f"forbidden={result.forbidden_hit} page={result.page_correct} sources={result.retrieved_sources}"
        for result in report.results
        if result.forbidden_hit
        or result.phrases_hit is False
        or result.recall_hit is False
        or result.page_correct is False
        or (result.type == "unanswerable" and not result.abstained)
        or (result.type == "contradictory" and not result.conflict_detected)
        or (result.type != "contradictory" and result.conflict_detected)
        or (result.type != "unanswerable" and result.abstained)
    ]
    assert failures == [], "\n".join(failures)
    assert report.citation_validity == 1
    assert report.citation_support_rate == 1
    assert report.claim_coverage == 1
    assert report.retrieval_recall_at_k == 1
    assert report.abstention_recall == 1
    assert report.abstention_precision == 1
    assert report.conflict_recall == 1
    assert report.conflict_false_positive_rate == 0


def test_cli_json_output_matches_the_schema(example_documents: Path, tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.setenv("GENERATION_PROVIDER", "extractive")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    index_dir = tmp_path / "index"
    assert cli.main(["index", str(example_documents), "--index-dir", str(index_dir)]) == 0
    capsys.readouterr()
    assert cli.main(
        [
            "ask",
            "What is Intervention X?",
            "--index-dir",
            str(index_dir),
            "--format",
            "json",
        ]
    ) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    response = AnswerResponse.model_validate(payload)
    required = {
        "question",
        "answer",
        "claims",
        "citations",
        "unanswered_questions",
        "conflicts",
        "abstained",
        "limitations",
    }
    assert required <= set(payload)
    assert required <= set(AnswerResponse.model_json_schema()["properties"])
    assert response.abstained is False
    assert response.citations
    assert all(citation.valid and citation.supports_claim for citation in response.citations)
    assert "morning light-exposure program" in response.claims[0].text

    capsys.readouterr()
    assert cli.main(["sources", "--index-dir", str(index_dir)]) == 0
    assert cli.main(["stats", "--index-dir", str(index_dir)]) == 0
    chunk_id = response.citations[0].chunk_id
    capsys.readouterr()
    assert cli.main(["show-source", chunk_id, "--index-dir", str(index_dir)]) == 0
    shown = capsys.readouterr().out
    assert chunk_id in shown
    assert "morning light-exposure program" in shown


def test_cli_errors_are_actionable(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.setenv("GENERATION_PROVIDER", "extractive")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    missing = cli.main(["ask", "What is known?", "--index-dir", str(tmp_path / "missing")])
    assert missing == 2
    error = capsys.readouterr().err
    assert "No index" in error
    assert "python cli.py index" in error

    empty = tmp_path / "empty"
    empty.mkdir()
    status = cli.main(["index", str(empty), "--index-dir", str(tmp_path / "index")])
    assert status == 2
    assert "No supported documents" in capsys.readouterr().err
