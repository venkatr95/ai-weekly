from pathlib import Path

from meeting_memory.config import Settings
from meeting_memory.diarization import coerce_diarization_label
from meeting_memory.pipeline import MeetingMemory


def test_diarization_labels_stay_anonymous():
    assert coerce_diarization_label("Alex", 1) == "SPEAKER_01"
    assert coerce_diarization_label("speaker_00", 3) == "SPEAKER_00"
    assert coerce_diarization_label(None, 1) is None


def test_manual_speaker_map_survives_reingest(tmp_path: Path):
    path = tmp_path / "labels.txt"
    path.write_text(
        "\n".join(
            [
                "# Meeting: Labels",
                "# Date: 2026-11-01",
                "[00:00:10] SPEAKER_00: I will deliver the API by December 5.",
            ]
        ),
        encoding="utf-8",
    )
    memory = MeetingMemory(Settings(index_dir=tmp_path / "index"))
    memory.ingest(path)
    before = memory.items(kind="commitment")[0]
    assert before.owner == "SPEAKER_00"
    meeting = memory.map_speakers("Labels", "SPEAKER_00", "Alex", 0.75)
    assert meeting.speaker_map["SPEAKER_00"] == "Alex"
    assert meeting.speaker_map_confidence["SPEAKER_00"] == 0.75
    assert meeting.utterances[0].speaker == "Alex"
    assert meeting.utterances[0].source_speaker == "SPEAKER_00"
    mapped = memory.items(kind="commitment")[0]
    assert mapped.owner == "Alex"
    memory.ingest(path)
    again = memory.items(kind="commitment")[0]
    assert again.owner == "Alex"
    assert memory.meetings()[0].speaker_map["SPEAKER_00"] == "Alex"
