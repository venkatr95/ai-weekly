# Implementation plan

The milestones in the PRD are implemented in this repository.

| Requirement | Status |
| --- | --- |
| Plain text, threads, headers, and `.eml` input | Done in `parser.py` |
| Whitespace, quotes, signatures, and disclaimers | Done in `preprocessor.py` |
| Tasks with ids, owners, deadlines, priority, status, dependencies, and evidence | Done in `extractor.py` |
| Explicit, suggested, and implied actions | Done |
| Relative dates resolved only from a message timestamp | Done in `dates.py` |
| Inferred dates marked as inferred | Done for "the day before" a dated task |
| Questions, confirmations, approvals, and missing information | Done |
| Sender commitments kept separate from recipient tasks | Done |
| Validated JSON and Markdown | Done in `schemas.py` and `report.py` |
| Draft reply that does not accept commitments | Done in `reply.py` |
| CLI and Python API | Done in `cli.py` and `pipeline.py` |
| Sending mail, calendar events, or external task assignment | Not built. Out of scope for version 1 |

The acceptance thread is `examples/launch_thread.txt`. `pytest -q` covers that thread, date resolution, quoted history, and the draft-reply rule.
