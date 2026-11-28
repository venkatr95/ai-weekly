from pathlib import Path

from meeting_memory.config import Settings
from meeting_memory.pipeline import MeetingMemory


def _memory(tmp_path: Path, history: Path) -> MeetingMemory:
    memory = MeetingMemory(Settings(index_dir=tmp_path / "index"))
    report = memory.ingest(history)
    assert report.meetings_added == 2
    return memory


def test_api_deadline_is_superseded(tmp_path: Path, history: Path):
    items = _memory(tmp_path, history).items(kind="commitment")
    original = next(item for item in items if item.deadline_iso == "2026-03-20")
    revised = next(item for item in items if item.deadline_iso == "2026-03-27")
    assert original.status == "superseded"
    assert original.superseded_by == revised.item_id
    assert revised.supersedes == original.item_id
    assert revised.status == "open"
    assert revised.owner == "Alex"
    assert revised.prior_deadline_iso == "2026-03-20"
    assert revised.evidence_type == "explicit"


def test_migration_notes_are_done_and_schema_review_stays_open(tmp_path: Path, history: Path):
    memory = _memory(tmp_path, history)
    notes = next(item for item in memory.items(kind="commitment") if "migration notes" in item.text)
    assert notes.status == "done"
    assert notes.status_evidence is not None
    assert "done" in notes.status_evidence.quote
    assert notes.status_evidence.meeting_name == "API follow-up"

    unresolved = memory.items(kind="question", status="unresolved")
    assert len(unresolved) == 1
    assert "schema review" in unresolved[0].text.casefold()

    deployment_question = next(item for item in memory.items(kind="question") if "deployment" in item.text)
    assert deployment_question.status == "resolved"
    assert deployment_question.status_evidence is not None
    assert deployment_question.status_evidence.quote == "I own the deployment."


def test_inferred_runbook_is_not_treated_as_an_agreement(tmp_path: Path, history: Path):
    tasks = _memory(tmp_path, history).items(kind="task")
    runbook = next(item for item in tasks if "runbook" in item.text)
    assert runbook.evidence_type == "inferred"
    assert runbook.owner is None
    assert runbook.status == "open"
