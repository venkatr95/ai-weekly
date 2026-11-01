# Python API

```python
from email_to_action import analyze, ActionList, PublicReport

action: ActionList = analyze(
    source,
    settings=None,
    received_at=None,
    tone="professional",
    include_reply=True,
)
```

`source` is a path, a path string, or email text. `received_at` is an ISO-8601 timestamp used only when a message has no `Date` header. `tone` is `professional`, `friendly`, `concise`, or `formal`. `include_reply=False` leaves `draft_reply` empty. The return value has already passed Pydantic validation.

## ActionList

The internal model keeps the fields the extractor checks.

| Field | Meaning |
| --- | --- |
| `subject` | Subject of the first message that has one |
| `participants` | Senders, recipients, and people or teams mentioned as owners |
| `messages` | Chronological messages, oldest first when timestamps allow it |
| `tasks` | Extracted work. Ids are `task-1`, `task-2` |
| `questions` | Questions, confirmations, approvals, and missing information |
| `commitments` | Work a participant already said they would do |
| `draft_reply` | Editable reply, or `None` when no reply was requested |
| `warnings` | Parse notes, conflicting deadlines, and completion notes |
| `reference_timestamp` | The supplied `received_at` value, when one was passed |

## Task

| Field | Meaning |
| --- | --- |
| `task_id` | `task-1`, `task-2`, in extraction order |
| `description` | Action, without the deadline phrase |
| `owner` | `name`, `email`, `role`, `confidence`, `ambiguous` |
| `deadline` | Wording, normalized date, time, timezone, precision, confidence, kind, source message |
| `priority` | `high`, `medium`, `low`, or `unknown` |
| `priority_explanation` | Why that priority was chosen |
| `status` | `open`, `completed`, or `blocked` |
| `dependencies` | Other internal task ids. No cycles |
| `related_questions` | Question ids from the same request |
| `message_id` | Source message |
| `supporting_text` | Exact line from that message |
| `evidence_type` | `explicit_request`, `suggested_action`, `implied_action`, or `commitment` |
| `confidence` | Confidence in the extraction, separate from deadline confidence |

Owner roles are `named`, `recipient`, `sender`, `team`, and `unassigned`. An unknown owner has `name=None`.

Deadline kinds are `explicit`, `inferred`, `none`, and `unresolved`. An inferred deadline has a normalized date. An unresolved deadline does not. An empty deadline has neither wording nor a normalized date.

## Public JSON

`render_json(action)` validates a `PublicReport` and returns it. This is the `--format json` document.

| Field | Meaning |
| --- | --- |
| `email_metadata` | `subject`, `sender`, and `received_at`. `received_at` is the latest message timestamp, then the supplied received-at value, then null |
| `summary` | Counts of actions and questions. It does not say the work must be done |
| `actions` | Public tasks. `task_id` is `T001`. `owner` is a string or null. `status` `pending` means internal `open` |
| `questions` | `question_id` such as `Q001`, `text`, `owner`, and the source wording |
| `draft_reply` | `subject`, `body`, `tone`, `requires_approval`, and `accepts_commitments`. Null when no reply was requested |
| `uncertainties` | Missing years, unresolved dates, ambiguous owners, inferred dates, and completion notes that need confirmation |
| `source_references` | Message id, sender, subject, date, and the evidence lines. The full body is not copied here |
| `requires_approval` | Always true |

A deadline object has `original_text`, `normalized_date`, `type`, and the stored time, timezone, precision, and confidence. `type` is `explicit`, `inferred`, or `unresolved`. When the email states no deadline, `deadline` is null.

Validation fails if the reply promises the work ("I will", "I'll") or claims it is already complete ("I already sent"). `accepts_commitments` cannot be true.

## Rendering

```python
from email_to_action.report import render_json, render_markdown, to_public

render_markdown(action)
render_json(action)
to_public(action)  # PublicReport
```
