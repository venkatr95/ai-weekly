import sys
import wave
from pathlib import Path

from meeting_memory.config import Settings
from meeting_memory.pipeline import MeetingMemory


def _wav(path: Path) -> None:
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\x00\x00" * 1600)


def test_sidecar_transcript_is_used_for_audio(tmp_path: Path):
    audio = tmp_path / "standup.wav"
    _wav(audio)
    sidecar = tmp_path / "standup.vtt"
    sidecar.write_text(
        "\n".join(
            [
                "WEBVTT",
                "",
                "Meeting: Standup",
                "Date: 2026-05-01",
                "",
                "00:00:02.000 --> 00:00:05.000",
                "<v Alex>I will bring the notes by Friday.",
            ]
        ),
        encoding="utf-8",
    )
    memory = MeetingMemory(Settings(index_dir=tmp_path / "index"))
    report = memory.ingest(tmp_path)
    assert report.meetings_added == 1
    assert report.files_needs_transcription == []
    meeting = memory.meetings()[0]
    assert meeting.origin == "sidecar"
    assert meeting.name == "Standup"
    assert meeting.utterances[0].speaker == "Alex"
    assert meeting.utterances[0].start == "00:00:02"
    assert meeting.source_path == str(audio.resolve())


def test_audio_without_a_transcript_needs_transcription(tmp_path: Path):
    audio = tmp_path / "bare.wav"
    _wav(audio)
    memory = MeetingMemory(Settings(index_dir=tmp_path / "index"))
    report = memory.ingest(audio)
    assert report.meetings_added == 0
    assert any("bare.wav" in item for item in report.files_needs_transcription)


def test_optional_whisper_adapter_uses_segment_times(tmp_path: Path, monkeypatch):
    audio = tmp_path / "voice.wav"
    _wav(audio)

    class Segment:
        def __init__(self, text: str, start: float, end: float):
            self.text = text
            self.start = start
            self.end = end

    class FakeModel:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def transcribe(self, path, **kwargs):
            return [Segment(" We decided to use Postgres for the database. ", 1.5, 4.0)], None

    fake = type("FakeWhisper", (), {"WhisperModel": FakeModel})
    monkeypatch.setitem(sys.modules, "faster_whisper", fake)
    memory = MeetingMemory(
        Settings(index_dir=tmp_path / "index", transcriber="whisper", whisper_model="tiny")
    )
    report = memory.ingest(audio)
    assert report.meetings_added == 1
    meeting = memory.meetings()[0]
    assert meeting.origin == "whisper"
    assert meeting.utterances[0].speaker is None
    assert meeting.utterances[0].start == "00:00:01.500"
    assert meeting.utterances[0].end == "00:00:04"
    answer = memory.ask("What decisions were made about the database?")
    assert answer.abstained is False
    assert "Postgres" in answer.text
