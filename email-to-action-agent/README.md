# Email-to-Action Agent

The Email-to-Action Agent reads a pasted email or a thread and turns it into work: tasks, owners, deadlines, priorities, dependencies, questions, and an editable draft reply.

The draft lists the requests. It does not promise that you will do them, and it does not send email.

Version 1 uses deterministic rules. The same email produces the same JSON. A deadline is normalized only when the message timestamp makes that date recoverable. A relative date such as "Friday" stays unresolved when the message has no timestamp.

## Demo

The bundled launch note asks Alex for three items, asks John to review copy, and suggests a meeting after the other work.

```bash
python cli.py analyze --input examples/launch_thread.txt
```

| Task | Owner | Deadline | Priority |
| --- | --- | --- | --- |
| Complete the landing page. | Alex | November 10 | High |
| Send the final product screenshots to the marketing team. | Alex | November 7 | High |
| Confirm whether the pricing page is ready. | Alex | Not specified | Medium |
| Review the campaign copy. | John | November 8 | High |
| Schedule a final review meeting. | Unassigned | After other tasks | Medium |

The open question is "Is the pricing page ready?" The scheduling task depends on the four earlier tasks. High priority on the dated requests comes from "We need to finalize" in the message, not from the deadline alone. A dated request with no urgency language stays medium.

## Install

Python 3.11 or newer. On this machine use the `py` launcher if `python` is not on `PATH`.

```bash
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

macOS and Linux use `source .venv/bin/activate`.

## Use

```bash
python cli.py analyze --input examples/email.txt
python cli.py analyze --input examples/email_thread.txt
python cli.py analyze --input examples/email.txt --received-at "2026-11-01T09:00:00+01:00"
python cli.py analyze --input examples/email.txt --format json
python cli.py analyze --input examples/email.txt --tone professional
python cli.py analyze --input examples/email.txt --no-reply
pytest -q
```

`--tone` is `professional`, `friendly`, `concise`, or `formal`. `--no-reply` extracts actions and skips the draft. `--received-at` fills in a timestamp only for messages that have no `Date` header. A month and day such as November 7 stays un-normalized when that timestamp is absent. The checked-in report is `examples/expected_output.json`.

JSON from `--format json` is a public report: `email_metadata`, `summary`, `actions`, `questions`, `draft_reply`, `uncertainties`, and `source_references`. Unknown owners and dates are null. Task ids in that report are `T001`. An open task is reported as `pending`. The draft is not sent.

From Python:

```python
from email_to_action import analyze

action = analyze("examples/launch_thread.txt")
print(action.tasks[0].owner.name)
print(action.draft_reply.body)

dated = analyze("examples/email.txt", received_at="2026-11-01T09:00:00+01:00", tone="formal")
print(dated.tasks[1].deadline.normalized_date)
```

`analyze()` accepts a file path or the email text. A string that is an existing file path is read as a file. `include_reply=False` returns `draft_reply=None`.

## Documentation

- [Installation](docs/INSTALLATION.md)
- [Configuration](docs/CONFIGURATION.md)
- [Usage](docs/USAGE.md)
- [Architecture](ARCHITECTURE.md)
- [Python API](docs/API.md)
- [Security](docs/SECURITY.md)
- [Integrations](docs/INTEGRATIONS.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Product requirements](PRD.md)
