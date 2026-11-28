# PRD: Meeting-Memory Agent

## 1. Product vision

Build an AI-powered assistant that converts meeting recordings, transcripts, and written notes into a searchable knowledge base of decisions, commitments, action items, and unresolved questions.

Users can upload meeting recordings or transcripts and ask natural-language questions about what happened.

The system should answer questions such as:

- Who agreed to deliver the API?
- When is the API expected to be ready?
- What decisions were made about the database?
- Who owns the deployment?
- Which questions remain unresolved?
- What did the team agree in the previous meeting?
- Were any previous commitments changed?

Every answer must include supporting evidence with meeting names, speaker information where available, and timestamps or source references.

## 2. Unique value proposition (UVP)

Most meeting tools generate summaries and action lists.

This project creates a persistent, searchable memory of what people actually said and agreed to do.

**Its unique value proposition is turning meetings into an evidence-backed record of organizational commitments and decisions.**

Key differentiators:

- Search across multiple meetings.
- Retrieve decisions and commitments using natural language.
- Identify who made a commitment.
- Extract deadlines and responsible owners.
- Preserve exact timestamps and supporting transcript passages.
- Track unresolved questions.
- Compare commitments across meetings.
- Distinguish explicit agreements from inferred responsibilities.
- Answer questions using recorded evidence rather than invented recollections.

## 3. Target users

- Software development teams.
- Product managers.
- Project managers.
- Engineering managers.
- Consultants.
- Remote teams.
- Researchers conducting interviews.
- Founders coordinating projects.
- Teams managing recurring meetings.

## 4. Goals and non-goals

### Goals

1. Accept audio recordings and meeting transcripts.
2. Convert recordings into timestamped transcripts.
3. Identify speakers when possible.
4. Extract decisions, commitments, tasks, deadlines, and unresolved questions.
5. Store meeting information in a searchable index.
6. Answer natural-language questions across multiple meetings.
7. Provide timestamped supporting evidence.
8. Track commitments and their status over time.
9. Generate meeting summaries and action lists.
10. Provide Markdown and JSON outputs.
11. Provide a CLI and reusable Python API.
12. Include automated tests and complete documentation.

### Non-goals for version 1

- Real-time meeting participation.
- Automatically joining online meetings.
- Recording meetings without consent.
- Automatically assigning tasks in external systems.
- Automatically sending meeting follow-ups.
- Identifying people through biometric recognition.
- Replacing professional meeting or project-management platforms.
- Treating inferred commitments as confirmed agreements.

## 5. Core user experience

### Example input

A meeting recording or transcript:

**Meeting:** API Integration Planning

**Participants:** Alex, Sarah, John

**Transcript:**

[00:02:14] Sarah: We need the API integration ready before the next release.

[00:02:25] Alex: I can take responsibility for the API implementation.

[00:02:32] Sarah: Can you have it ready by December 5?

[00:02:38] Alex: Yes, I'll deliver the API implementation by December 5.

[00:03:10] John: I'll handle the database migration.

[00:03:20] Sarah: We still need to decide whether authentication will use OAuth or API keys.

### Example question

"Who agreed to deliver the API and by when?"

### Expected answer

Evidence found.

**Alex agreed to deliver the API implementation by December 5.**

Supporting evidence:

- Meeting: API Integration Planning
- Speaker: Alex
- Timestamp: 00:02:38
- Transcript: "Yes, I'll deliver the API implementation by December 5."

**Related commitments**

- John: Handle the database migration.
- Deadline: Not specified.

**Unresolved question**

- Should API authentication use OAuth or API keys?

The system must distinguish between an explicit commitment, a suggested action, and a question that has not been resolved.

That transcript is `examples/meetings/planning_transcript.txt`. `examples/meetings/sprint_review_transcript.txt` is a later meeting that changes the API date, closes the database migration, and decides on OAuth. `examples/questions.json` scores the combined corpus. `examples/expected_answers.json` records the planning-only answer. An earlier two-meeting corpus used for regression tests lives in `examples/history`.

## 6. Functional requirements

### FR-1: Meeting ingestion

Support audio recordings (WAV, MP3, M4A, and the other formats listed in the installation docs), text transcripts (TXT and Markdown), structured transcript JSON, meeting metadata, and optional participant lists.

Each stored meeting keeps a meeting id, title, date and optional time, participants, recording filename when the source is audio, transcript, processing status, language, and source metadata. Users can upload one meeting or a directory of meetings.

### FR-2: Speech-to-text transcription

Convert audio to text through a replaceable provider. Preserve timestamps. Keep speaker diarization anonymous when a provider supplies it. Preserve the original audio path. Report transcription failures. Store language and confidence when the provider supplies them. The default provider reads a sidecar transcript and does not invent speech. An optional local Whisper-compatible provider is documented in `docs/TRANSCRIPTION.md`.

### FR-3: Timestamp preservation

Every transcript segment stores a segment id, start time, end time when the source has one, speaker id when available, text, and optional confidence. Times are stored as seconds and shown as clock times. The agent never invents an end time. A plain-text transcript with no clock time is cited by line number.

### FR-4: Speaker identification

Speakers come from participant lists, transcript labels, or anonymous diarization labels. Users can map a label such as `SPEAKER_00` to a name. Unknown speakers stay unknown. The agent does not guess a person's identity from voice characteristics. Manual corrections are stored with the meeting and reapplied when that file is indexed again. A confidence value can be stored with the map.

### FR-5: Decision extraction

Extract decisions with an id, description, supporting passage, speakers, meeting, timestamp, status, and topic. Distinguish confirmed decisions, proposed decisions, rejected proposals, deferred decisions, and decisions that still need confirmation.

### FR-6: Commitment extraction

Identify statements where a participant explicitly takes responsibility. Each commitment has an id, responsible person, action, deadline when one was stated, status, original wording, timestamp, meeting, and extraction uncertainty. "I can take responsibility" is an unconfirmed offer. "Someone should update the documentation" is inferred and is not a confirmed commitment.

### FR-7: Action item extraction

Extract tasks with an id, description, owner, deadline, priority when the words state one, a dependency when the words say "depends on", a related decision when linking finds one, meeting, evidence, and status. Statuses cover new, updated, completed, deferred, and cancelled work. Open explicit commitments are committed. Done items are completed. Dropped items are cancelled.

### FR-8: Deadline extraction

Support explicit dates, relative deadlines, clock times, and event deadlines such as "before the next release". The meeting date is the reference for relative dates. If the meeting date is missing, the original wording is kept and the normalized date stays empty. Explicit dates stay distinct from inferred or event wording.

### FR-9: Unresolved question detection

Identify questions and topics that stay unresolved, including "we still need to decide whether ...". A question is resolved only when a later utterance in the stored meetings answers it. A shared short token such as "api" is not enough to treat two different topics as the same question.

### FR-10: Searchable meeting memory

Search commitments by person, decisions and tasks by topic, meetings by date, unresolved questions, and discussions of a feature. Retrieval is hybrid: keyword overlap, a local hashed embedding that reranks those hits, and metadata filters. Results keep meeting and timestamp metadata. A vector hit with no keyword overlap is not cited.

### FR-11: Question-answering

Answer natural-language questions from retrieved passages. Include the meeting name and timestamp, cite the supporting statement, and abstain when the evidence is insufficient. If meetings disagree, show the timeline, including the earlier wording, instead of silently keeping one. Conflicting open deadlines are reported as conflicts.

### FR-12: Commitment tracking over time

Track proposed, committed, in progress, completed, deferred, cancelled, and unconfirmed states. Link an updated commitment to the earlier one. Detect changed deadlines and ownership changes. Keep the history. Do not mark a commitment completed only because a later meeting never mentions it.

### FR-13: Structured output

Pydantic models validate meetings, items, and answers. A JSON answer includes `question`, `answer`, `evidence` (`meeting_id`, `meeting_title`, `speaker`, `timestamp_start`, `timestamp_end`, `quote`), `related_commitments` (`owner`, `action`, `deadline`), `unresolved_questions`, and `abstained`. `timestamp_end` is null when the source has no end time. The planning example's start is 158.0 seconds (00:02:38). Citations are checked against stored segments before an answer is returned. A quote that is not in the cited meeting, or a timestamp that does not belong to that quote, is removed. If no valid citation remains, the answer abstains.

### FR-14: Report generation

`report` and `summary` write Markdown or JSON with the summary, participants, decisions, commitments, tasks, deadlines, and unresolved questions. Question answers include the direct answer, evidence, related commitments, conflicts, and unanswered questions.

### FR-15: CLI

`transcribe`, `import`, `index`, `ingest`, `ask`, `commitments --owner`, `unresolved`, `show`, `report`, `search`, `delete`, and `speakers map` are implemented. `show` and `report` accept a meeting id, the title, or an `M001` label for the earliest meeting in the current index. `pytest -q` runs the tests.

### FR-16: Security and privacy

Transcripts are untrusted and are never executed. The tool does not join meetings or record them. API keys, if a future provider needs one, belong in environment variables. Errors do not log transcript bodies. External provider handling is documented in `docs/TRANSCRIPTION.md` and `docs/SECURITY.md`. Storage is local. `delete` and `MEETING_RETENTION_DAYS` are the deletion and retention controls. Multi-user access control is not built; keep the index on a machine you control.

## 7. Recommended architecture

The recommended tree in the original brief separates one module per concern. This repository keeps that boundary, with a few combined modules:

| Recommended role | Module in this repository |
|---|---|
| Transcript parsing and timestamps | `transcripts.py`, `timestamps.py` |
| Audio loading and transcription | `audio_loader.py`, `transcription.py` |
| Diarization policy | `diarization.py` |
| Speaker mapping | `speaker_mapper.py` |
| Extraction | `extraction.py`, `dates.py`, `linking.py` |
| Storage | `pipeline.py` (`corpus.json`) |
| Retrieval and answering | `retrieval.py`, `answering.py` |
| Evidence checks | `evidence_validator.py` |
| Schemas | `schemas.py` |

`IMPLEMENTATION_PLAN.md` records which recommended libraries are not bundled.

## 8. Technology stack

Python 3.11+, Pydantic, and pytest are required. The CLI uses argparse. Speech-to-text is optional local faster-whisper. Retrieval is local keyword overlap plus a hashed embedding. The index is a JSON corpus. SQLite, Chroma, sentence-transformers, Pyannote, FFmpeg, and a cloud language model are not required for the default path.

## 9. Core processing workflow

1. Load a recording or a transcript.
2. Read meeting metadata.
3. Transcribe audio only when a provider is selected and no sidecar exists.
4. Store timestamped segments, without inventing missing times.
5. Apply a saved speaker map when one exists.
6. Extract decisions, commitments, tasks, owners, deadlines, and unresolved questions.
7. Link those items across meetings.
8. Index the records.
9. Answer a question from retrieved evidence.
10. Validate every quote and timestamp against stored segments.
11. Return the answer, the citations, related commitments, and unresolved questions.

## 10. Evaluation strategy

`examples/questions.json` is a behavioral check of the indexed sample meetings. `examples/history_questions.json` keeps the earlier March corpus check. Human-annotated measures such as word-error rate need a speech provider and a reference transcript; this repository does not invent those scores. Citation validity, abstention, commitment and deadline behavior, and cross-meeting revisions are what the automated tests measure. See `docs/EVALUATION.md`.

## 11. Acceptance criteria

- [x] Accept audio recordings and existing transcripts.
- [x] Support common audio formats.
- [x] Generate timestamped transcripts.
- [x] Preserve speaker labels where available.
- [x] Allow manual speaker mapping.
- [x] Extract decisions.
- [x] Extract explicit commitments.
- [x] Identify action owners.
- [x] Extract deadlines.
- [x] Identify unresolved questions.
- [x] Store searchable meeting information.
- [x] Answer questions across multiple meetings.
- [x] Include timestamped evidence in answers.
- [x] Validate citations against stored transcript segments.
- [x] Detect conflicting commitments and decisions.
- [x] Track commitment changes over time.
- [x] Generate Markdown and JSON reports.
- [x] Provide a working CLI.
- [x] Pass automated tests.
- [x] Include example meeting transcripts and questions.
- [x] Provide documentation.
- [x] Document transcription limitations and privacy safeguards.

## 12. Implementation milestones

Milestones 1 through 6 from the brief are represented in the current tree: transcript ingest, optional audio transcription, extraction, searchable memory, historical linking, and tests plus security notes. `IMPLEMENTATION_PLAN.md` is the status note for this repository.

## 13. Definition of done

A developer can install the application, import a transcript or a sidecar recording, index it, and ask who agreed to do what, by when, and where that sentence appears.

Every factual answer cites a stored transcript passage. When the transcript does not establish an answer, the system says so.
