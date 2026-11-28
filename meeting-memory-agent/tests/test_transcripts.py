from pathlib import Path

from meeting_memory.transcripts import parse_transcript


def test_speaker_lines_keep_names_and_timestamps(tmp_path: Path):
    path = tmp_path / "2026-03-04-planning.txt"
    path.write_text(
        "\n".join(
            [
                "# Meeting: API planning",
                "# Date: 2026-03-04",
                "# Participants: Alex, Priya",
                "",
                "[00:01:12] Alex: I will deliver the API by March 20.",
                "[00:01:40] Priya: We decided to use Postgres.",
            ]
        ),
        encoding="utf-8",
    )
    parsed = parse_transcript(path)
    assert parsed.name == "API planning"
    assert parsed.held_on == "2026-03-04"
    assert parsed.participants[:2] == ["Alex", "Priya"]
    assert parsed.utterances[0].speaker == "Alex"
    assert parsed.utterances[0].start == "00:01:12"
    assert parsed.utterances[0].text == "I will deliver the API by March 20."


def test_vtt_voice_tags(tmp_path: Path):
    path = tmp_path / "standup.vtt"
    path.write_text(
        "\n".join(
            [
                "WEBVTT",
                "",
                "00:00:01.000 --> 00:00:04.000",
                "<v Alex>I will deliver the API by March 20.",
                "",
                "00:00:05.500 --> 00:00:08.000",
                "<v Priya>We decided to use Postgres.",
            ]
        ),
        encoding="utf-8",
    )
    parsed = parse_transcript(path)
    assert parsed.utterances[0].speaker == "Alex"
    assert parsed.utterances[0].start == "00:00:01"
    assert parsed.utterances[0].end == "00:00:04"
    assert parsed.utterances[1].start == "00:00:05.500"
    assert "Postgres" in parsed.utterances[1].text


def test_srt_without_a_speaker(tmp_path: Path):
    path = tmp_path / "notes.srt"
    path.write_text(
        "\n".join(
            [
                "1",
                "00:00:01,000 --> 00:00:04,000",
                "Alex: I will deliver the API by March 20.",
                "",
                "2",
                "00:00:05,000 --> 00:00:08,000",
                "We decided to use Postgres.",
            ]
        ),
        encoding="utf-8",
    )
    parsed = parse_transcript(path)
    assert parsed.utterances[0].speaker == "Alex"
    assert parsed.utterances[1].speaker is None
    assert parsed.utterances[1].text == "We decided to use Postgres."


def test_json_transcript(tmp_path: Path):
    path = tmp_path / "meeting.json"
    path.write_text(
        """
        {
          "meeting": "API planning",
          "date": "2026-03-04",
          "participants": ["Alex"],
          "utterances": [
            {"speaker": "Alex", "start": 72.5, "end": 80, "text": "I will deliver the API by March 20."}
          ]
        }
        """,
        encoding="utf-8",
    )
    parsed = parse_transcript(path)
    assert parsed.name == "API planning"
    assert parsed.held_on == "2026-03-04"
    assert parsed.utterances[0].start == "00:01:12.500"
    assert parsed.utterances[0].end == "00:01:20"


def test_markdown_notes_use_line_numbers(tmp_path: Path):
    path = tmp_path / "retro.md"
    path.write_text(
        "\n".join(
            [
                "# Meeting: Retro notes",
                "# Date: 2026-04-02",
                "",
                "**Alex:** I will close the audit by April 9.",
            ]
        ),
        encoding="utf-8",
    )
    parsed = parse_transcript(path)
    assert parsed.name == "Retro notes"
    assert parsed.held_on == "2026-04-02"
    assert parsed.utterances[0].speaker == "Alex"
    assert parsed.utterances[0].start is None
    assert parsed.utterances[0].line_start == 4


def test_filename_supplies_a_missing_date_and_name(tmp_path: Path):
    path = tmp_path / "2026-03-04-api-planning.txt"
    path.write_text("Alex: I will deliver the API by March 20.\n", encoding="utf-8")
    parsed = parse_transcript(path)
    assert parsed.name == "api planning"
    assert parsed.held_on == "2026-03-04"
