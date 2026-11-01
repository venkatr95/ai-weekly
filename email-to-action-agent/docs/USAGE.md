# Usage

## CLI

```bash
python cli.py analyze --input examples/launch_thread.txt
python cli.py analyze --input message.eml --format json --output actions.json
python cli.py analyze --output actions.md < email.txt
```

`--input` accepts `.txt` and `.eml`. Omit it to read the email from stdin. `--format` is `markdown` or `json`. Markdown is the default. Exit code `0` means an action list was written. Exit code `2` means the input could not be read.

## What the summary contains

- A table of tasks, owners, deadlines, priority, and status.
- Questions that need a response.
- Dependencies by task id.
- Commitments already made by a participant.
- The reason for each priority.
- A draft reply.

`Not specified` means the email did not give a deadline. `After other tasks` means the deadline is an event such as "once these items are complete". A relative date with no message timestamp is shown with `(unresolved)`.

## Python

```python
from email_to_action import analyze
from email_to_action.report import render_markdown

action = analyze("examples/launch_thread.txt")
print(render_markdown(action))
```

A string that contains a newline is email text. A string without a newline is a file path when that file exists, and email text otherwise.

## Thread shape

These forms are understood:

- One message with `From`, `To`, `Cc`, `Date` or `Sent`, and `Subject`.
- Several of those header blocks in one paste. When every message has a timestamp, they are sorted oldest first.
- `-----Original Message-----` and `On Monday, 3 Nov 2026, Sarah wrote:`.
- A `>` quoted copy of an earlier message that still has headers.

Put a `Date` header on the message when the body says "Friday" or "tomorrow" and you want a calendar date.
