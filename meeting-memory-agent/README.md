# Meeting-memory agent

Turns meeting transcripts and recordings into a local, searchable record of decisions, commitments, tasks, and unresolved questions.

Answers quote the meeting, the speaker when one was recorded, and a timestamp or line number. If the index has no matching record, the agent abstains. It does not fill the gap from general knowledge.

The default path is offline. No API key is required. Extraction is rule-based: "we decided" and "I will" are explicit agreements, and "should" stays an inferred responsibility.

## Install

```bash
cd meeting-memory-agent
py -3 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Python 3.11 or newer. Run commands from this directory. `pytest` from the collection root collects other projects and fails.

## Ask the sample meetings

```bash
python cli.py import examples/meetings/planning_transcript.txt
python cli.py ask "Who agreed to deliver the API and by when?"
python cli.py index examples/meetings
python cli.py evaluate
```

`examples/meetings/planning_transcript.txt` is the API Integration Planning meeting. Alex agrees to deliver the API implementation by December 5. John takes the database migration with no date. Authentication is still undecided. "I can take responsibility" is an offer, not the agreement that gets cited.

`sprint_review_transcript.txt` is the later meeting. Alex moves the date to December 12, John finishes the migration, and the team decides on OAuth. Asking the same question after both meetings shows both dates.

An answer for the planning transcript alone looks like this:

```text
## Answer

Alex agreed to deliver the API implementation by December 5. This is an explicit commitment. The deadline is 2026-12-05.

## Evidence

- API Integration Planning (2026-11-20) — Alex at 00:02:38 — "Yes, I'll deliver the API implementation by December 5."

## Related commitments

- John: Handle the database migration. Deadline: not specified.

## Unresolved questions

- We still need to decide whether authentication will use OAuth or API keys.
```

A question about a subject that was never discussed abstains and cites nothing. `examples/history` keeps an earlier March corpus used by the regression tests.

## Commands

| Command | What it does |
|---|---|
| `ingest PATH` / `index PATH` | Index a transcript, a recording, or a directory. `--rebuild` replaces the index. |
| `import PATH` | Index an existing transcript. |
| `transcribe PATH` | Transcribe a recording with local faster-whisper and index the result. |
| `ask QUESTION` | Answer from the index. `--format markdown` or `json`. |
| `search QUERY` | Keyword search across items. Optional `--owner`, `--kind`, and `--status`. |
| `meetings` | List indexed meetings. `M001` is the earliest meeting in the current index. |
| `show MEETING` | Print one transcript. Accepts an id, a title, or `M001`. |
| `summary MEETING` / `report MEETING` | Decisions, commitments, tasks, and questions. `--format markdown` or `json`. |
| `commitments` | List commitments and tasks. `--owner Alex` and `--status open` filter them. |
| `questions` / `unresolved` | List questions. `questions` defaults to unresolved. Use `--status all` for every question. |
| `decisions` | List decisions. |
| `compare TOPIC` | Show matching records across meetings in time order. |
| `speakers map MEETING --label SPEAKER_00 --name Alex` | Map an anonymous label. Optional `--confidence`. |
| `delete MEETING` | Remove one meeting. `delete --all --yes` clears the index. |
| `evaluate` | Score `examples/questions.json` against a fresh index of the sample meetings. |

`--index-dir` selects the index. The default is `data/index`.

## Python API

```python
from pathlib import Path
from meeting_memory import MeetingMemory
from meeting_memory.config import Settings

memory = MeetingMemory(Settings(index_dir=Path("data/index")))
memory.ingest(Path("examples/meetings"))
answer = memory.ask("Who agreed to deliver the API and by when?")
summary = memory.summary("API Integration Planning")
```

`answer.abstained` is true when nothing in the index supports an answer. `answer.evidence` holds the quoted passages. `answer.related_commitments` and `answer.unresolved_questions` are separate from the answer sentence. `evidence.start_seconds` is the start time in seconds. `evidence.end` stays empty when the transcript line has no end time.

## Input

Transcripts:

- Speaker lines: `[00:01:12] Alex: I will deliver the API by March 20.`
- WebVTT, including `<v Alex>` voice tags, and SRT
- JSON with an `utterances` list (`speaker`, `start`, `end`, `text`)
- Markdown or text notes: `**Alex:** ...` or `Alex: ...`
- A header for `# Meeting:`, `# Date:`, `# Time:`, `# Participants:`, and `# Language:`

Recordings (`.wav`, `.mp3`, `.m4a`, `.flac`, `.ogg`, `.webm`, `.mp4`):

- Put a transcript next to the file with the same name, such as `standup.wav` and `standup.vtt`.
- Or set `MEETING_TRANSCRIBER=whisper` and install `faster-whisper`. That path is local. It does not identify speakers.

A recording with neither a sidecar nor whisper is reported as needing transcription and is not indexed.

## Tests

```bash
py -3 -m pytest
```

`py -3 -m pytest` covers parsing, dates, extraction, cross-meeting links, the planning example, speaker mapping, citation checks, retrieval, audio sidecars, the optional whisper adapter, the CLI, and both question sets.

## Docs

- [PRD.md](PRD.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [docs/USAGE.md](docs/USAGE.md)
- [docs/API.md](docs/API.md)
- [docs/CONFIGURATION.md](docs/CONFIGURATION.md)
- [docs/INSTALLATION.md](docs/INSTALLATION.md)
- [docs/SECURITY.md](docs/SECURITY.md)
- [docs/EVALUATION.md](docs/EVALUATION.md)
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- [docs/TRANSCRIPTION.md](docs/TRANSCRIPTION.md)
