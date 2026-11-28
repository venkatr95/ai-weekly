# Python API

```python
from pathlib import Path
from meeting_memory import MeetingMemory
from meeting_memory.config import Settings

memory = MeetingMemory(Settings(index_dir=Path("data/index")))
```

`MeetingMemory()` with no settings uses `data/index` and the sidecar transcriber. `Settings.from_env(index_dir=...)` reads `.env` and the `MEETING_*` variables. An explicit `Settings` field wins over the environment.

## Methods

| Method | Returns |
|---|---|
| `ingest(path, rebuild=False)` | `IngestReport` |
| `ask(question)` | `Answer` |
| `compare(topic)` | `Answer` |
| `meetings()` | Meetings sorted by date, then name |
| `get_meeting(key)` | One meeting by id, exact name, or a unique substring. Raises `NotFoundError` when the key is missing or ambiguous. |
| `summary(key)` | `MeetingSummary`, including `markdown` |
| `items(kind=None, status=None)` | `MemoryItem` records. `kind` is `decision`, `commitment`, `task`, `question`, or `status`. |
| `search(query, kind=None, owner=None, status=None)` | Keyword hits, reranked locally. |
| `map_speakers(key, label, name, confidence=1.0)` | Store a label-to-name map and re-extract. |
| `delete(key)` | Remove one meeting and rebuild links. Returns the meeting name. |
| `clear()` | Delete every meeting in the index. |

`ingest` raises `InputError` when the path does not exist. A file that is too large, not UTF-8, or not a transcript is listed on the report (`files_failed`, `files_skipped`, or `files_needs_transcription`) and does not abort the rest of the directory. `meetings_added == 0` means nothing new was stored. The CLI exits 1 in that case.

`get_meeting` accepts a meeting id, an exact or unique title, or `M001` for the earliest meeting.

`ask` on an empty index returns `abstained=True` and `reason="no_meetings"`. A question with no matching record uses `reason="no_matching_evidence"`. A drafted citation that is not a stored segment uses `reason="invalid_citations"`. All three have an empty `evidence` list.

`answer.text` is the sentence a person reads. `answer.related_commitments` lists other explicit commitments from the same meetings. `answer.unresolved_questions` lists questions from those meetings that are still open. `evidence.start_seconds` is the start in seconds. `evidence.end_seconds` is set only when the utterance has an end time.

## Item fields that matter

- `evidence_type`: `explicit` or `inferred`
- `status`: `open`, `done`, `dropped`, `superseded`, `resolved`, `unresolved`, or `unconfirmed`
- `commitment_state`: `proposed`, `committed`, `in_progress`, `completed`, `deferred`, `cancelled`, or `unconfirmed`
- `decision_status`: `confirmed`, `proposed`, `rejected`, `deferred`, or `needs_confirmation`
- `deadline_iso`, `deadline_wording`, `deadline_kind` (`explicit`, `relative`, `event`, `time`, `unresolved`, `none`)
- `prior_deadline_iso` when a later sentence changed the date
- `supersedes` / `superseded_by`
- `evidence.quote` is the sentence copied from the transcript
- `status_evidence` quotes the later sentence that marked a commitment done or dropped

`evaluate(memory, load_questions(path))` in `meeting_memory.evaluation` scores a JSON list of questions. Each object may set `abstain`, `answer_contains`, `answer_excludes`, `evidence_contains`, `speaker`, `meeting`, and `timestamp`.

Rendered Markdown and JSON live in `meeting_memory.rendering`.
