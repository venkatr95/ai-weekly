# Usage

## CLI

```bash
python cli.py analyze --input examples/email.txt
python cli.py analyze --input examples/email_thread.txt
python cli.py analyze --input examples/email.txt --received-at "2026-11-01T09:00:00+01:00"
python cli.py analyze --input examples/email.txt --format json
python cli.py analyze --input examples/email.txt --tone professional
python cli.py analyze --input examples/email.txt --no-reply
python cli.py analyze --output actions.md < examples/email.txt
```

`--input` accepts `.txt` and `.eml`. Omit it to read the email from stdin. `--format` is `markdown` or `json`. Markdown is the default.

`--received-at` is an ISO-8601 timestamp. It is the reference for relative dates only on messages that have no `Date` or `Sent` header. A message that already has a timestamp keeps that timestamp.

`--tone` is `professional` (the default), `friendly`, `concise`, or `formal`. `--no-reply` extracts actions and omits the draft. Exit code `0` means a report was written. Exit code `2` means the input or the timestamp could not be read.

## What the summary contains

- An email summary with the subject and the count of actions and questions.
- A checklist of tasks, owners, deadlines, priority, and status.
- Owners and deadlines, listed again by public id (`T001`).
- Questions that need a response.
- Dependencies by public task id.
- Commitments already made by a participant.
- The reason for each priority.
- A draft reply, or a line that no reply was requested.
- Uncertainties, including missing years, unresolved relative dates, and unassigned owners.

`Not specified` means the email did not give a deadline. `After other tasks` means the deadline is an event such as "once these items are complete". A relative date with no message timestamp is shown with `(unresolved)`. `Pending` in the checklist is an open task. Public JSON calls that same state `pending`.

The draft quotes deadline wording from the email. It asks for a year or an owner when those are missing. It does not claim that a completed status is confirmed, and it is not sent.

## Python

```python
from email_to_action import analyze
from email_to_action.report import render_json, render_markdown

action = analyze(
    "examples/email.txt",
    received_at="2026-11-01T09:00:00+01:00",
    tone="professional",
    include_reply=True,
)
print(render_markdown(action))
print(render_json(action))
```

A string that contains a newline is email text. A string without a newline is a file path when that file exists, and email text otherwise.

`examples/expected_output.json` is the public JSON for `examples/email.txt` with no received-at timestamp. `examples/expected_reply.md` is the draft for that file.

## Thread shape

These forms are understood:

- One message with `From`, `To`, `Cc`, `Date` or `Sent`, and `Subject`.
- Several of those header blocks in one paste. When every message has a timestamp, they are sorted oldest first.
- `-----Original Message-----` and `On Monday, 3 Nov 2026, Sarah wrote:`.
- A `>` quoted copy of an earlier message that still has headers.

Put a `Date` header on the message, or pass `--received-at`, when the body says "Friday" or "tomorrow" and you want a calendar date.
