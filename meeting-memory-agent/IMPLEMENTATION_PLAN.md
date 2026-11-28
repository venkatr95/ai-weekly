# Implementation plan

Version 1 is the offline record described in [PRD.md](PRD.md). These pieces are in the tree.

1. Transcript parsers for speaker lines, WebVTT, SRT, JSON, and notes, including meeting date, title, and participants.
2. Audio ingest through a same-name sidecar transcript. Optional local faster-whisper when `MEETING_TRANSCRIBER=whisper`.
3. Sentence extraction for decisions, explicit commitments, explicit tasks, inferred tasks, questions, completions, and cancellations.
4. Deadline resolution that refuses to invent a year, and that keeps an "instead of" date in the meeting year.
5. Cross-meeting linking for superseded deadlines, completed commitments, and questions that a later utterance answers or repeats as still open.
6. A JSON index and a question router with Markdown and JSON rendering.
7. CLI, Python API, bundled meetings, nine scored questions, and unit tests.

The product non-goals are in [PRD.md](PRD.md). They are not the same as these implementation choices:

- Extraction is rule-based and local. There is no cloud language model on the default path.
- "I can" and "I could" are stored as unconfirmed offers. They are not the citation for "who agreed".
- "Should" and "needs to" stay inferred. "We still need to decide whether ..." is an unresolved question, not a confirmed decision.
- Diarization labels stay `SPEAKER_NN`. A name is applied only through `speakers map`.
- Keyword search is reranked with a local hash embedding. Chroma and sentence-transformers are not bundled.
- The index is `corpus.json`, not SQLite.
- faster-whisper is optional. FFmpeg and Pyannote are not bundled.
- There is no web UI, no ticket writer, and no mail sender.

A later meeting that never mentions a commitment does not mark it done. A month and day without a meeting date keeps its wording and leaves the ISO date empty. The planning example's end timestamp stays empty because the source line has no end time.
