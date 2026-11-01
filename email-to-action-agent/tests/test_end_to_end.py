"""The CLI and Python API return the same validated action list."""

import json
from email.message import EmailMessage as MimeMessage
from pathlib import Path

import pytest

from cli import main
from email_to_action import analyze
from email_to_action.config import Settings
from email_to_action.errors import EmailActionError
from email_to_action.report import render_json

ROOT = Path(__file__).resolve().parents[1]
LAUNCH = ROOT / "examples" / "launch_thread.txt"


def test_example_file_matches_the_product_sample():
    action = analyze(LAUNCH)
    assert action.subject == "Q4 Product Launch"
    assert [task.owner.name for task in action.tasks] == ["Alex", "Alex", "Alex", "John", None]
    assert action.questions[0].text == "Is the pricing page ready?"
    assert action.tasks[-1].dependencies == ["task-1", "task-2", "task-3", "task-4"]
    assert "I'll send" not in action.draft_reply.body


def test_cli_writes_json(capsys, tmp_path: Path):
    output = tmp_path / "actions.json"
    code = main(["analyze", "--input", str(LAUNCH), "--format", "json", "--output", str(output)])
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert printed["actions"][0]["description"] == saved["actions"][0]["description"]
    assert len(saved["actions"]) == 5
    assert saved["actions"][0]["task_id"] == "T001"
    assert saved["actions"][0]["status"] == "pending"
    assert saved["email_metadata"]["sender"] == "Sarah"
    assert saved["email_metadata"]["received_at"] is None
    assert saved["draft_reply"]["accepts_commitments"] is False
    assert saved["draft_reply"]["requires_approval"] is True
    assert saved["requires_approval"] is True


def test_eml_file_and_missing_file(tmp_path: Path):
    mime = MimeMessage()
    mime["From"] = "Sarah <sarah@example.com>"
    mime["To"] = "Alex <alex@example.com>"
    mime["Subject"] = "Notes"
    mime["Date"] = "Mon, 02 Nov 2026 09:00:00 -0500"
    mime.set_content("Hi Alex,\n\nPlease send the report by Friday.\n")
    path = tmp_path / "notes.eml"
    path.write_bytes(mime.as_bytes())
    action = analyze(path)
    assert action.tasks[0].owner.email == "alex@example.com"
    assert action.tasks[0].deadline.normalized_date == "2026-11-06"
    with pytest.raises(EmailActionError):
        analyze(tmp_path / "missing.txt")


def test_empty_input_and_size_limit_fail():
    with pytest.raises(EmailActionError):
        analyze("  \n")
    with pytest.raises(EmailActionError):
        analyze("Please send the report by Friday.", settings=Settings(max_chars=10))


def test_cli_received_at_tone_and_no_reply(capsys):
    code = main(
        [
            "analyze",
            "--input",
            str(LAUNCH),
            "--received-at",
            "2026-11-01T09:00:00+01:00",
            "--tone",
            "concise",
            "--format",
            "json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    screenshots = next(item for item in payload["actions"] if "screenshots" in item["description"])
    assert screenshots["deadline"]["normalized_date"] == "2026-11-07"
    assert screenshots["deadline"]["type"] == "explicit"
    assert payload["email_metadata"]["received_at"] == "2026-11-01T09:00:00+01:00"
    assert "not commitments" in payload["draft_reply"]["body"].lower()
    assert "please confirm" in payload["draft_reply"]["body"].lower()

    code = main(["analyze", "--input", str(LAUNCH), "--no-reply", "--format", "json"])
    assert code == 0
    skipped = json.loads(capsys.readouterr().out)
    assert skipped["draft_reply"] is None
    assert skipped["actions"]


def test_cli_rejects_a_bad_timestamp(capsys):
    code = main(["analyze", "--input", str(LAUNCH), "--received-at", "next Friday"])
    assert code == 2
    assert "received-at" in capsys.readouterr().err


def test_checked_in_examples_match_the_analyzer():
    action = analyze(ROOT / "examples" / "email.txt")
    saved = json.loads((ROOT / "examples" / "expected_output.json").read_text(encoding="utf-8"))
    assert json.loads(render_json(action)) == saved
    reply = (ROOT / "examples" / "expected_reply.md").read_text(encoding="utf-8")
    assert action.draft_reply.subject in reply
    assert action.draft_reply.body in reply
    thread = analyze(ROOT / "examples" / "email_thread.txt")
    assert thread.tasks[0].deadline.normalized_date == "2026-11-06"
    assert thread.tasks[0].status.value == "completed"
    assert "does not confirm completion" in thread.draft_reply.body.lower()


def test_cli_rejects_empty_stdin(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", _Empty())
    code = main(["analyze"])
    assert code == 2
    assert "No email text" in capsys.readouterr().err


class _Empty:
    def read(self) -> str:
        return ""
