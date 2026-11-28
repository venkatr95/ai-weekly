from pathlib import Path

from meeting_memory.config import Settings
from meeting_memory.pipeline import MeetingMemory


def _memory(tmp_path: Path) -> MeetingMemory:
    return MeetingMemory(Settings(index_dir=tmp_path / "index"))


def test_planning_meeting_answers_who_agreed_and_by_when(tmp_path: Path, examples: Path):
    memory = _memory(tmp_path)
    report = memory.ingest(examples / "planning_transcript.txt")
    assert report.meetings_added == 1
    answer = memory.ask("Who agreed to deliver the API and by when?")
    assert answer.abstained is False
    assert "Alex agreed to deliver the API implementation by December 5." in answer.text
    assert "explicit commitment" in answer.text
    evidence = answer.evidence[0]
    assert evidence.meeting_name == "API Integration Planning"
    assert evidence.speaker == "Alex"
    assert evidence.start == "00:02:38"
    assert evidence.start_seconds == 158.0
    assert evidence.end is None
    assert evidence.end_seconds is None
    assert evidence.quote == "Yes, I'll deliver the API implementation by December 5."
    assert all("I can take responsibility" not in item.quote for item in answer.evidence)
    john = next(item for item in answer.related_commitments if item.owner == "John")
    assert john.action == "Handle the database migration"
    assert john.deadline is None
    assert any("OAuth" in question and "API keys" in question for question in answer.unresolved_questions)
    meeting = memory.meetings()[0]
    for item in answer.evidence:
        assert any(item.quote in utterance.text for utterance in meeting.utterances)


def test_authentication_is_unresolved_until_a_later_decision(tmp_path: Path, examples: Path):
    memory = _memory(tmp_path)
    memory.ingest(examples / "planning_transcript.txt")
    pending = memory.ask("What did we decide about authentication?")
    assert pending.abstained is False
    assert "No confirmed decision" in pending.text
    assert "OAuth" in pending.text and "API keys" in pending.text
    assert "Explicit decision" not in pending.text

    memory.ingest(examples / "sprint_review_transcript.txt")
    decided = memory.ask("What did we decide about authentication?")
    assert "Explicit decision" in decided.text
    assert "OAuth" in decided.text
    assert "API keys" not in decided.text
    revised = memory.ask("Who agreed to deliver the API and by when?")
    assert "December 12" in revised.text
    assert "December 5" in revised.text
    assert any("December 5" in item.quote for item in revised.evidence)
    assert any("December 12" in item.quote for item in revised.evidence)


def test_a_later_silent_meeting_does_not_complete_a_commitment(tmp_path: Path, examples: Path):
    memory = _memory(tmp_path)
    memory.ingest(examples / "planning_transcript.txt")
    silent = tmp_path / "silent.txt"
    silent.write_text(
        "\n".join(
            [
                "# Meeting: Status standup",
                "# Date: 2026-11-27",
                "# Participants: Alex, Sarah",
                "[00:00:05] Sarah: Thanks for joining.",
            ]
        ),
        encoding="utf-8",
    )
    memory.ingest(silent)
    delivery = next(item for item in memory.items(kind="commitment") if "December 5" in item.text)
    assert delivery.status == "open"
    assert delivery.commitment_state == "committed"
