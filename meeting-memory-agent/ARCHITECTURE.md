# Architecture

The agent indexes meetings into one local JSON file, derives structured items from the utterances, and answers by selecting those items. It does not call a language model.

```text
transcript or recording
        |
        v
  transcripts.py / transcription.py
        |
        v
  Meeting + utterances
        |
        v
  extraction.py  -->  decisions, commitments, tasks, questions, status lines
        |
        v
  linking.py     -->  done, superseded, resolved
        |
        v
  data/index/corpus.json
        |
        v
  answering.py   -->  Answer with quotes, or an abstention
        |
        v
  evidence_validator.py  -->  drop quotes that are not stored segments
```

## Modules

| Module | Role |
|---|---|
| `transcripts.py` | Speaker lines, WebVTT, SRT, JSON, and notes. |
| `transcription.py` | Sidecar files, and optional local faster-whisper. |
| `dates.py` | Deadlines. The meeting date fills a missing year. It does not invent one. |
| `extraction.py` | One item per sentence. Explicit and inferred stay distinct. |
| `linking.py` | A later sentence can complete, drop, or replace an earlier commitment, or resolve a question. |
| `textutil.py` | Tokens used to tell that two sentences are about the same topic. A single generic verb such as "own" is not enough. |
| `answering.py` | Routes who, when, decision, unresolved, previous-meeting, and change questions. |
| `audio_loader.py` | Format and size check before a recording is read. |
| `diarization.py` | Turns a non-anonymous diarizer label into `SPEAKER_NN`. |
| `speaker_mapper.py` | Applies a saved label-to-name map. It does not listen to audio. |
| `retrieval.py` | Keyword filter plus a local hashed embedding rerank. |
| `evidence_validator.py` | Checks every cited quote and timestamp against stored utterances. |
| `pipeline.py` | `MeetingMemory`: ingest, ask, search, speaker map, delete, summary. |
| `rendering.py` | Markdown and JSON, including related commitments and unresolved questions. |
| `evaluation.py` | Scores `examples/questions.json`. |

`cli.py` is a thin wrapper. Library callers use `MeetingMemory`.

## What gets stored

Each meeting keeps its name, date, optional time, participants, language, processing status, source path, origin (`transcript`, `sidecar`, or `whisper`), recording filename when the source is audio, speaker map, and utterances. Each utterance keeps speaker, the original label, start and end clock times, start and end seconds, text, line number, and optional confidence. An end time is stored only when the source has one.

Each item keeps kind, owner, deadline, evidence type, status, topic tokens, and the verbatim sentence as evidence. A completion or a revision also points at the other item. Status is recomputed from the utterances on every ingest, so re-indexing the same file does not stack duplicate links.

## How a question is answered

The router looks at the wording. "Unresolved" is checked before "changed", and "changed" before "previous meeting", so "Were any previous commitments changed?" reports revisions rather than the earlier meeting.

Topic words are the question with the scaffolding removed ("who", "decision", "previous", "meeting"). An item matches when it shares two topic words, or one specific word of five letters or more. "API" matches on its own when it is the only topic word.

A who or when answer prefers the current item over one that a later meeting superseded. The current item still cites the earlier passage when the deadline changed. Decisions list every matching decision. Unresolved questions list only questions that a later utterance did not answer. If the index is empty, or no item matches, the answer abstains and cites nothing.

"No commitment was revised" and "no unresolved questions are recorded" are answers about the index, not abstentions.

## Index

`data/index/corpus.json` is the whole corpus. It is gitignored. A corrupt file raises `CorruptIndexError` instead of being repaired in place. `--rebuild` deletes it before the new ingest.

Transcript text is data. Patterns extract items. Instructions inside a transcript do not change the router or suppress citations.
