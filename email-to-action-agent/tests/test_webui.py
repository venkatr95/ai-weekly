"""The web UI uses the same analyzer as the CLI."""

from email.message import EmailMessage as MimeMessage
from pathlib import Path

import pytest

from email_to_action.errors import EmailActionError
from streamlit_app import action_rows, analyze_text, analyze_upload

ROOT = Path(__file__).resolve().parents[1]
LAUNCH = ROOT / "examples" / "launch_thread.txt"


def test_launch_thread_rows_match_the_product_sample():
    action = analyze_text(
        LAUNCH.read_text(encoding="utf-8"),
        received_at=None,
        tone="professional",
        include_reply=True,
    )
    rows = action_rows(action)
    assert [row["Owner"] for row in rows] == ["Alex", "Alex", "Alex", "John", "Unassigned"]
    assert [row["Deadline"] for row in rows] == [
        "November 10",
        "November 7",
        "Not specified",
        "November 8",
        "After other tasks",
    ]
    assert rows[0]["Task"] == "T001"
    assert rows[0]["Status"] == "Pending"
    assert rows[0]["Priority"] == "High"
    assert "I'll send" not in action.draft_reply.body


def test_pasted_path_is_read_as_text(tmp_path: Path):
    target = tmp_path / "note.txt"
    target.write_text(
        "From: Sarah\nSubject: Hidden\n\nPlease send the ZEBRA-TASK-99 by Friday.\n",
        encoding="utf-8",
    )
    action = analyze_text(str(target), received_at=None, tone="professional", include_reply=False)
    assert "ZEBRA-TASK-99" not in action.model_dump_json()
    assert action.subject != "Hidden"
    assert action.draft_reply is None


def test_upload_eml_and_text_and_bad_encoding():
    mime = MimeMessage()
    mime["From"] = "Sarah <sarah@example.com>"
    mime["To"] = "Alex <alex@example.com>"
    mime["Subject"] = "Notes"
    mime["Date"] = "Mon, 02 Nov 2026 09:00:00 -0500"
    mime.set_content("Hi Alex,\n\nPlease send the report by Friday.\n")
    action = analyze_upload(
        "notes.eml",
        mime.as_bytes(),
        received_at=None,
        tone="formal",
        include_reply=True,
    )
    assert action.tasks[0].deadline.normalized_date == "2026-11-06"
    assert action.draft_reply.tone == "formal"

    pasted = analyze_upload(
        "launch.txt",
        LAUNCH.read_bytes(),
        received_at=None,
        tone="concise",
        include_reply=False,
    )
    assert pasted.subject == "Q4 Product Launch"
    assert pasted.draft_reply is None

    with pytest.raises(EmailActionError, match="UTF-8"):
        analyze_upload("notes.txt", b"\xff", received_at=None, tone="professional", include_reply=True)


def test_empty_text_and_bad_timestamp():
    with pytest.raises(EmailActionError, match="empty"):
        analyze_text(" \n", received_at=None, tone="professional", include_reply=True)
    with pytest.raises(EmailActionError, match="ISO-8601"):
        analyze_text(LAUNCH.read_text(encoding="utf-8"), received_at="next Friday", tone="professional", include_reply=True)


def test_page_analyzes_the_sample_and_rejects_a_bad_timestamp():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30)
    app.run()
    assert not app.exception

    app.button(key="analyze").click().run()
    assert not app.exception
    assert app.session_state.action.subject == "Q4 Product Launch"
    assert app.session_state.action.tasks[0].owner.name == "Alex"
    assert "I'll" not in app.session_state.draft_body
    frame = app.dataframe[0].value
    assert list(frame["Owner"]) == ["Alex", "Alex", "Alex", "John", "Unassigned"]
    assert list(frame["Deadline"]) == [
        "November 10",
        "November 7",
        "Not specified",
        "November 8",
        "After other tasks",
    ]

    app.text_input(key="received_at").set_value("next Friday").run()
    app.button(key="analyze").click().run()
    assert any("ISO-8601" in item.value for item in app.error)
    assert app.session_state.action is None
