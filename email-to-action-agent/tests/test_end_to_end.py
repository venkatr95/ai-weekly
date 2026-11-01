"""The CLI and Python API return the same validated action list."""

import json
from email.message import EmailMessage as MimeMessage
from pathlib import Path

import pytest

from cli import main
from email_to_action import analyze
from email_to_action.config import Settings
from email_to_action.errors import EmailActionError

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
    assert printed["tasks"][0]["description"] == saved["tasks"][0]["description"]
    assert len(saved["tasks"]) == 5
    assert saved["draft_reply"]["accepts_commitments"] is False


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


def test_cli_rejects_empty_stdin(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", _Empty())
    code = main(["analyze"])
    assert code == 2
    assert "No email text" in capsys.readouterr().err


class _Empty:
    def read(self) -> str:
        return ""
