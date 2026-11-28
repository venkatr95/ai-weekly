# Troubleshooting

## `pytest` fails with import errors for other projects

Run it from `meeting-memory-agent`. The collection root has several test suites, and each one expects its own `pythonpath`.

## Ingest prints "Needs transcription"

The file is audio and there is no `same-name.vtt`, `.srt`, `.json`, `.txt`, or `.md` beside it. Add that sidecar, or install `faster-whisper` and set `MEETING_TRANSCRIBER=whisper`. The agent will not invent speech.

## Whisper import error

`MEETING_TRANSCRIBER=whisper` is set and `faster-whisper` is not installed. Install it in this virtualenv, or switch the transcriber back to `sidecar`.

## The answer abstains

`reason` is `no_meetings` when nothing has been ingested, `no_matching_evidence` when no decision, commitment, task, or question shares a topic word with the question, or `invalid_citations` when a drafted quote is not in the stored transcript. The abstention text does not add facts from other meetings.

A supported negative is different. "No previous commitment was revised" and "No unresolved questions are recorded" mean the index was searched and those records are absent. `abstained` is false.

## A person was not named

Speaker labels come from the transcript (`Alex:` or `<v Alex>`). Whisper segments have `speaker=null`. "I will" then has no owner. The evidence still quotes the line.

## A date is missing or looks one year off

There is no meeting date, so "Friday" and "March 20" stay unresolved or, for a bare month and day, cannot be placed. Add `# Date: 2026-03-04` or a `2026-03-04-` file-name prefix.

A new deadline before the meeting date rolls to the next year. An "instead of" date does not. See [CONFIGURATION.md](CONFIGURATION.md).

## "Should" did not become a decision

That is intentional. Only "decided", "agreed", "will", "own", and "commit" are explicit. "Should" is an inferred responsibility and is labeled that way.

## The index will not load

`corpus.json` is invalid. The CLI prints `CorruptIndexError` and leaves the file alone. Point `--index-dir` at a new directory, or delete the bad file and ingest again.

## A file was skipped or failed

Unsupported extensions are skipped. Oversized files and invalid UTF-8 are failures. A JSON file with no `utterances` list is not a transcript. The message names the file and not its contents.
