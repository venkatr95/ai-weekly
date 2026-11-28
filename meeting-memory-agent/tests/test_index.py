from pathlib import Path

from meeting_memory.config import Settings
from meeting_memory.errors import CorruptIndexError
from meeting_memory.pipeline import MeetingMemory
import pytest


def test_reload_and_reingest_do_not_duplicate(tmp_path: Path, history: Path):
    index = tmp_path / "index"
    first = MeetingMemory(Settings(index_dir=index))
    report = first.ingest(history)
    assert report.meetings_total == 2
    again = MeetingMemory(Settings(index_dir=index))
    second = again.ingest(history)
    assert second.meetings_added == 2
    assert second.meetings_total == 2
    assert len(again.meetings()) == 2
    answer = again.ask("Who owns the deployment?")
    assert answer.evidence[0].quote == "I own the deployment."


def test_rebuild_drops_meetings_that_are_not_in_the_new_path(tmp_path: Path, history: Path):
    index = tmp_path / "index"
    memory = MeetingMemory(Settings(index_dir=index))
    memory.ingest(history)
    one = next(history.glob("*.txt"))
    report = memory.ingest(one, rebuild=True)
    assert report.meetings_total == 1
    assert len(memory.meetings()) == 1


def test_corrupt_index_is_rejected(tmp_path: Path):
    index = tmp_path / "index"
    index.mkdir()
    (index / "corpus.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(CorruptIndexError):
        MeetingMemory(Settings(index_dir=index)).ask("Who owns the deployment?")
