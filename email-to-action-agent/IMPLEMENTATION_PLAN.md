# Implementation plan

The milestones in the PRD are implemented in this repository.

| Requirement | Status |
| --- | --- |
| Plain text, threads, headers, and `.eml` input | Done in `parser.py` |
| Whitespace, quotes, signatures, and disclaimers | Done in `preprocessor.py` |
| Tasks with ids, owners, deadlines, priority, status, dependencies, and evidence | Done in `extractor.py` |
| Explicit, suggested, and implied actions | Done |
| Relative dates resolved only from a message timestamp or `--received-at` | Done in `dates.py` and `pipeline.py` |
| Inferred dates marked as inferred | Done for "the day before" a dated task |
| Questions, confirmations, approvals, and missing information | Done |
| Sender commitments kept separate from recipient tasks | Done |
| Conflicting deadlines kept as an uncertainty instead of a silent replacement | Done |
| Completion and blocked notes recorded, and left unconfirmed in the draft | Done |
| Public JSON (`T001`, null owners and dates, uncertainties) and Markdown | Done in `schemas.py` and `report.py` |
| Draft reply with four tones that does not accept commitments | Done in `reply.py` |
| CLI flags `--received-at`, `--tone`, `--format`, and `--no-reply` | Done in `cli.py` |
| Hand-labeled precision and recall | Done in `tests/test_evaluation.py` |
| Read-only Gmail and Outlook adapters, separate from the pipeline | Done in `integrations/` |
| Sending mail, calendar events, or external task assignment | Not built |

The acceptance thread is `examples/launch_thread.txt`. The public sample is `examples/email.txt` with `examples/expected_output.json`. `pytest -q` covers that thread, date resolution, quoted history, the draft-reply rule, and the mailbox adapters with a fake opener.

IMAP is documented as the same read-only contract and is not connected.
