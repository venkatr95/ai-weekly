# Usage

Run every command from `meeting-memory-agent`.

## Index transcripts

```bash
python cli.py import examples/meetings/planning_transcript.txt
python cli.py ask "Who agreed to deliver the API and by when?"
python cli.py index examples/meetings
python cli.py meetings
python cli.py show M001
python cli.py report M001 --format markdown
python cli.py commitments --owner Alex
python cli.py unresolved
```

`ingest` accepts one file or a directory. Indexing the same path again replaces that meeting and rebuilds links. `--rebuild` drops meetings that are not in the new path.

A directory walk skips hidden files and files that are not transcripts or recordings. A `.vtt`, `.srt`, `.json`, `.txt`, or `.md` file used as the sidecar for a recording is not indexed a second time.

## Ask

```bash
python cli.py ask "Who agreed to deliver the API?"
python cli.py ask "Which questions remain unresolved?" --format json
python cli.py compare "API delivery"
python cli.py commitments --status open
python cli.py questions
python cli.py decisions
```

`questions` defaults to unresolved questions. `--status all` shows resolved and superseded questions too.

JSON answers use the `Answer` schema: `question`, `answer`, `abstained`, `reason`, `text`, `evidence`, `related_commitments`, `unresolved_questions`, `conflicts`, and `items`. Each evidence object has `meeting_name`, `meeting_title`, `held_on`, `speaker`, `start`, `start_seconds`, `timestamp_start`, `end`, `end_seconds`, `timestamp_end`, and `quote`. `timestamp_end` is null when the source line has no end time.

`M001` means the earliest meeting in the current index. `show` and `report` also accept the meeting id printed by `meetings` and the meeting title.

```bash
python cli.py speakers map "Labels" --label SPEAKER_00 --name Alex --confidence 0.8
python cli.py delete "API Integration Planning"
python cli.py delete --all --yes
python cli.py search "database migration" --owner John
python cli.py transcribe notes/standup.wav
```

`transcribe` forces the local Whisper provider for that command. `import` and `index` follow `MEETING_TRANSCRIBER`. `delete --all` does nothing unless `--yes` is present.

## Recordings

```text
notes/standup.wav
notes/standup.vtt
```

```bash
python cli.py ingest notes/standup.wav
```

The wav is the source. The vtt supplies speakers and timestamps. Without the vtt, ingest reports that the recording needs a sidecar or `MEETING_TRANSCRIBER=whisper`, and it does not invent a transcript.

## Transcript shapes

Speaker lines:

```text
# Meeting: API planning
# Date: 2026-03-04
# Participants: Alex, Priya, Sam

[00:01:12] Alex: I will deliver the API by March 20.
```

WebVTT voice tags (`<v Alex>`), SRT cues (`Name: text` or plain text), and JSON:

```json
{
  "meeting": "API planning",
  "date": "2026-03-04",
  "utterances": [
    {"speaker": "Alex", "start": "00:01:12", "text": "I will deliver the API by March 20."}
  ]
}
```

`start` may be a timestamp string or a number of seconds. Notes without timestamps cite a line number.

A file name `2026-03-04-api-planning.txt` supplies the date and the name when the file has no header.

## What the extractor treats as an agreement

| Wording | Result |
|---|---|
| "We decided..." or "We agreed..." | Explicit decision |
| "I will...", "I'll...", "I own...", "Jordan will..." | Explicit commitment. The owner is the speaker or the named person. |
| "Alex, please..." | Explicit task |
| "Someone should..." | Inferred task. Not an agreement. |
| A question, or "still unresolved" / "open question" | Question |
| "The migration notes are done." | Marks the earlier matching commitment done |
| "by March 27 instead of March 20" | Revises the earlier matching commitment |

"I can see the problem" is not a commitment. The sentence has to say will, own, or commit.
