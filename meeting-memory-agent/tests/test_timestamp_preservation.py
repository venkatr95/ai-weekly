from meeting_memory.timestamps import format_ms, parse_ms, to_seconds
from meeting_memory.transcripts import parse_transcript
from pathlib import Path


def test_clock_times_become_seconds_without_inventing_an_end(tmp_path: Path):
    path = tmp_path / "planning.txt"
    path.write_text(
        "[00:02:38] Alex: Yes, I'll deliver the API implementation by December 5.\n",
        encoding="utf-8",
    )
    parsed = parse_transcript(path)
    utterance = parsed.utterances[0]
    assert utterance.start == "00:02:38"
    assert utterance.end is None
    assert parse_ms(utterance.start) == 158_000
    assert to_seconds(utterance.start) == 158.0
    assert to_seconds(utterance.end) is None
    assert format_ms(158_000) == "00:02:38"


def test_plain_text_without_a_clock_keeps_the_line_number(tmp_path: Path):
    path = tmp_path / "notes.txt"
    path.write_text("Alex: I will deliver the API by Friday.\n", encoding="utf-8")
    parsed = parse_transcript(path)
    utterance = parsed.utterances[0]
    assert utterance.start is None
    assert utterance.end is None
    assert utterance.line_start == 1
    assert to_seconds(utterance.start) is None
