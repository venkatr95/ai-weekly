import json
from pathlib import Path

from cli import main


def test_cli_ingest_ask_and_summary(tmp_path: Path, history: Path, capsys):
    index = tmp_path / "index"
    assert main(["ingest", str(history), "--index-dir", str(index)]) == 0
    ingested = capsys.readouterr().out
    assert "Indexed 2 meetings" in ingested

    assert main(["ask", "Who owns the deployment?", "--index-dir", str(index), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["abstained"] is False
    assert payload["evidence"][0]["speaker"] == "Alex"
    assert payload["evidence"][0]["start"] == "00:02:18"
    assert payload["evidence"][0]["quote"] == "I own the deployment."

    assert main(["summary", "API planning", "--index-dir", str(index), "--format", "markdown"]) == 0
    summary = capsys.readouterr().out
    assert "Postgres" in summary
    assert "## Commitments" in summary

    assert main(["questions", "--index-dir", str(index)]) == 0
    questions = capsys.readouterr().out
    assert "schema review" in questions.casefold()
    assert "deployment" not in questions.casefold()


def test_cli_report_unresolved_and_owner_filter(tmp_path: Path, examples: Path, capsys):
    index = tmp_path / "index"
    assert main(["import", str(examples / "planning_transcript.txt"), "--index-dir", str(index)]) == 0
    capsys.readouterr()
    assert main(["commitments", "--owner", "Alex", "--index-dir", str(index)]) == 0
    commitments = capsys.readouterr().out
    assert "December 5" in commitments
    assert "database migration" not in commitments.casefold()
    assert main(["unresolved", "--index-dir", str(index)]) == 0
    unresolved = capsys.readouterr().out
    assert "OAuth" in unresolved
    assert main(["report", "M001", "--index-dir", str(index), "--format", "markdown"]) == 0
    report = capsys.readouterr().out
    assert "API Integration Planning" in report
    assert "Unconfirmed offer" in report
    assert main(["show", "M001", "--index-dir", str(index)]) == 0
    shown = capsys.readouterr().out
    assert "00:02:38" in shown
    assert "Language: en" in shown


def test_cli_evaluate(tmp_path: Path, examples: Path, questions_path: Path, capsys):
    output = tmp_path / "report.json"
    code = main(
        [
            "evaluate",
            "--meetings",
            str(examples),
            "--questions",
            str(questions_path),
            "--index-dir",
            str(tmp_path / "index"),
            "--output",
            str(output),
        ]
    )
    captured = capsys.readouterr().out
    assert code == 0, captured
    assert "Passed 9 of 9" in captured
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["passed"] == 9
    assert all(score["passed"] for score in report["scores"])
