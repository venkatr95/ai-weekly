from pathlib import Path

from meeting_memory.config import Settings
from meeting_memory.pipeline import MeetingMemory
from meeting_memory.rendering import render_answer_markdown


def _ready(tmp_path: Path, history: Path) -> MeetingMemory:
    memory = MeetingMemory(Settings(index_dir=tmp_path / "index"))
    memory.ingest(history)
    return memory


def test_prd_questions(tmp_path: Path, history: Path):
    memory = _ready(tmp_path, history)

    who = memory.ask("Who agreed to deliver the API?")
    assert who.abstained is False
    assert "Alex" in who.text
    assert "explicit commitment" in who.text
    assert any("I will deliver the API" in item.quote for item in who.evidence)

    when = memory.ask("When is the API expected to be ready?")
    assert "2026-03-27" in when.text
    assert "2026-03-20" in when.text
    assert any("March 27" in item.quote for item in when.evidence)

    decisions = memory.ask("What decisions were made about the database?")
    assert "Postgres" in decisions.text
    assert "Explicit decision" in decisions.text
    assert {item.evidence.meeting_name for item in decisions.items} == {"API planning", "API follow-up"}

    owner = memory.ask("Who owns the deployment?")
    assert owner.abstained is False
    assert "Alex" in owner.text
    assert owner.evidence[0].speaker == "Alex"
    assert owner.evidence[0].start == "00:02:18"
    assert owner.evidence[0].meeting_name == "API planning"
    assert owner.evidence[0].quote == "I own the deployment."
    rendered = render_answer_markdown(owner)
    assert "API planning" in rendered
    assert "00:02:18" in rendered
    assert "Alex" in rendered

    unresolved = memory.ask("Which questions remain unresolved?")
    assert "schema review" in unresolved.text.casefold()
    assert "Who owns the deployment" not in unresolved.text
    assert all(item.status == "unresolved" for item in unresolved.items)

    previous = memory.ask("What did the team agree in the previous meeting?")
    assert "API planning" in previous.text
    assert "Postgres" in previous.text
    assert "Alex" in previous.text
    assert "2026-03-27" not in previous.text
    assert "runbook" not in previous.text.casefold()

    changed = memory.ask("Were any previous commitments changed?")
    assert changed.abstained is False
    assert "Alex" in changed.text
    assert "2026-03-20" in changed.text
    assert "2026-03-27" in changed.text
    assert any("instead of March 20" in item.quote for item in changed.evidence)


def test_unknown_subject_abstains(tmp_path: Path, history: Path):
    answer = _ready(tmp_path, history).ask("What did we decide about the mobile app?")
    assert answer.abstained is True
    assert answer.reason == "no_matching_evidence"
    assert answer.evidence == []
    assert "Postgres" not in answer.text


def test_empty_index_abstains(tmp_path: Path):
    answer = MeetingMemory(Settings(index_dir=tmp_path / "index")).ask("Who owns the deployment?")
    assert answer.abstained is True
    assert answer.reason == "no_meetings"


def test_inferred_owner_is_labeled(tmp_path: Path, history: Path):
    answer = _ready(tmp_path, history).ask("Who will update the runbook?")
    assert answer.abstained is False
    assert "inferred" in answer.text
    assert "Sam" in answer.text
    assert "explicit commitment" not in answer.text
    assert answer.evidence[0].speaker == "Sam"


def test_compare_shows_both_api_deadlines(tmp_path: Path, history: Path):
    answer = _ready(tmp_path, history).compare("API delivery")
    assert answer.abstained is False
    assert "API planning" in answer.text
    assert "API follow-up" in answer.text
    assert "2026-03-20" in " ".join(item.deadline_iso or "" for item in answer.items)
    assert "2026-03-27" in " ".join(item.deadline_iso or "" for item in answer.items)


def test_summary_markdown_covers_decisions_tasks_and_questions(tmp_path: Path, history: Path):
    summary = _ready(tmp_path, history).summary("API planning")
    assert "Postgres" in summary.markdown
    assert "runbook" in summary.markdown
    assert "schema review" in summary.markdown.casefold()
    assert summary.held_on == "2026-03-04"
    assert any(item.status == "done" and "migration notes" in item.text for item in summary.commitments)
