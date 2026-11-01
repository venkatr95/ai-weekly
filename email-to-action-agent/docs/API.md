# Python API

```python
from email_to_action import analyze, ActionList

action: ActionList = analyze(source, settings=None)
```

`source` is a path, a path string, or email text. The return value has already passed Pydantic validation.

## ActionList

| Field | Meaning |
| --- | --- |
| `subject` | Subject of the first message that has one |
| `participants` | Senders, recipients, and people or teams mentioned as owners |
| `messages` | Chronological messages, oldest first when timestamps allow it |
| `tasks` | Extracted work |
| `questions` | Questions, confirmations, approvals, and missing information |
| `commitments` | Work a participant already said they would do |
| `draft_reply` | Editable reply. `accepts_commitments` is false |
| `warnings` | Unresolved dates, ambiguous owners, and parse notes |

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
| `dependencies` | Other task ids. No cycles |
| `related_questions` | Question ids from the same request |
| `message_id` | Source message |
| `supporting_text` | Exact line from that message |
| `evidence_type` | `explicit_request`, `suggested_action`, `implied_action`, or `commitment` |
| `confidence` | Confidence in the extraction, separate from deadline confidence |

Owner roles are `named`, `recipient`, `sender`, `team`, and `unassigned`.

Deadline kinds are `explicit`, `inferred`, `none`, and `unresolved`. An inferred deadline has a normalized date. An unresolved deadline does not. An empty deadline has neither wording nor a normalized date.

## Question

`question_id`, `text`, `original_wording`, `message_id`, `directed_to`, and `kind`. Kinds are `question`, `confirmation`, `missing_information`, and `approval`. `original_wording` is copied from the message. `text` may be a shorter question, such as "Is the pricing page ready?"

## DraftReply

`subject`, `body`, `tone`, `accepts_commitments`, and `notes`. Validation fails if the body promises the work with wording such as "I will" or "I'll".

## Rendering

```python
from email_to_action.report import render_json, render_markdown

render_markdown(action)
render_json(action)
```

`render_json` is the same object `model_dump(mode="json")` would produce.
