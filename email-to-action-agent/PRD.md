# PRD: Email-to-Action Agent

## 1. Product vision

Build an AI-powered assistant that reads email messages and converts them into structured, actionable information.

Users provide an email or an entire email thread. The agent extracts:

- Tasks and required actions.
- Deadlines and important dates.
- Responsible people and organizations.
- Requests and commitments.
- Priorities.
- Dependencies.
- Questions requiring responses.
- Suggested email replies.

The output is a validated JSON action list and an editable draft response.

## 2. Unique value proposition (UVP)

Most email AI tools summarize what an email says.

This project identifies what the recipient actually needs to do next.

**Its unique value proposition is converting communication into execution-ready actions without losing deadlines, ownership, or context.**

Key differentiators:

- Extracts explicit and implied action items.
- Identifies task owners and deadlines.
- Distinguishes confirmed dates from inferred dates.
- Tracks commitments made by different participants.
- Generates context-aware draft replies.
- Preserves links between actions and original email evidence.
- Produces structured JSON that can feed task-management systems.

## 3. Target users

- Professionals managing high email volumes.
- Project managers coordinating multiple stakeholders.
- Consultants managing client requests.
- Founders and small business owners.
- Administrative assistants.
- Teams coordinating work through email.
- Developers building email productivity integrations.

## 4. Goals and non-goals

### Goals

1. Accept pasted email messages and complete email threads.
2. Extract action items.
3. Identify task owners.
4. Extract explicit deadlines.
5. Interpret relative dates when the email date is available.
6. Identify priorities and dependencies.
7. Extract questions that need responses.
8. Generate a suitable draft reply.
9. Produce validated JSON.
10. Generate a readable Markdown summary.
11. Preserve source references for every extracted action.
12. Provide a CLI and reusable Python API.

### Non-goals for version 1

- Automatically sending emails.
- Automatically creating calendar events.
- Automatically assigning tasks in external systems.
- Making commitments on behalf of users.
- Sending replies without human approval.
- Replacing a full project-management platform.
- Inferring deadlines or owners without indicating uncertainty.

## 5. Core user experience

### Example input

**Email thread**

```
From: Sarah
Subject: Q4 Product Launch

Hi Alex,

We need to finalize the product launch materials.

Could you please:
- Complete the landing page by November 10.
- Send the final product screenshots to the marketing team by November 7.
- Confirm whether the pricing page is ready.

John, please review the campaign copy by November 8.

Let's schedule a final review meeting once these items are complete.

Thanks,
Sarah
```

### Expected output

**Action summary**

| Task | Owner | Deadline | Priority |
|---|---|---|---|
| Send final screenshots | Alex | November 7 | High |
| Review campaign copy | John | November 8 | High |
| Confirm pricing page readiness | Alex | Not specified | Medium |
| Complete landing page | Alex | November 10 | High |
| Schedule final review | Unassigned | After other tasks | Medium |

**Questions requiring a response**

- Is the pricing page ready?

**Suggested reply**

Hi Sarah,

Thanks for outlining the launch requirements.

I'll send the final screenshots by November 7 and complete the landing page by November 10. I'll also confirm the pricing page status.

I'll coordinate with John on the campaign copy review and follow up about scheduling the final review meeting once the remaining items are complete.

Best,
Alex

*This is an illustrative example. The reply must not imply that the user has accepted commitments they have not confirmed.*

The implementation keeps the five actions, owners, deadlines, and the pricing question. The draft it writes is deliberately more cautious than the sample reply above, because that sample accepts work the user has not confirmed. Descriptions in the tool keep the email's wording rather than shortening it.

## 6. Functional requirements

### FR-1: Email input

Support:

- Plain-text email.
- Complete email threads.
- Email headers.
- Sender and recipient fields.
- Subject lines.
- Timestamps.
- Quoted replies.
- Multiple participants.

Support `.eml` files as an additional input format where practical.

The parser should identify individual messages in a thread and preserve their chronological order.

### FR-2: Email preprocessing

- Normalize whitespace.
- Extract headers and metadata.
- Identify quoted reply sections.
- Separate original messages from quoted content.
- Preserve message timestamps.
- Identify signatures and disclaimers.
- Avoid treating historical quoted requests as new actions unless they remain unresolved.

### FR-3: Task extraction

Extract individual actionable tasks.

Each task should contain:

- Unique task ID.
- Task description.
- Responsible owner.
- Deadline.
- Priority.
- Status.
- Dependencies.
- Related questions.
- Original message reference.
- Exact supporting text.

Support explicit and implied actions, but distinguish between them.

Example:

"Please send the report by Friday."

Task:

- Description: Send the report.
- Owner: Recipient, if context establishes this.
- Deadline: Friday.
- Confidence: High.
- Evidence type: Explicit request.

Example:

"We should probably arrange a meeting."

Task:

- Description: Arrange a meeting.
- Owner: Unassigned.
- Deadline: Not specified.
- Confidence: Medium.
- Evidence type: Suggested action.

### FR-4: Owner extraction

Identify:

- Named individuals.
- Email addresses.
- Teams and departments.
- Sender.
- Recipient.
- Unassigned responsibilities.

Important rules:

- Do not automatically assign every task to the email recipient.
- Distinguish the person making the request from the person responsible for executing it.
- Preserve ambiguity when ownership cannot be determined.
- Use role-based descriptions when the person is not identified.

### FR-5: Deadline extraction

Support:

- Explicit dates.
- Relative dates such as tomorrow and next Friday.
- Time-based deadlines.
- Deadline ranges.
- Event-based deadlines.

Use the original email timestamp as the reference point for relative dates.

If no timestamp is available, mark relative dates as unresolved rather than inventing calendar dates.

Store:

- Original deadline wording.
- Normalized date when confidently resolvable.
- Optional time and timezone.
- Date precision.
- Confidence.
- Source message reference.

Distinguish between:

- Explicit deadlines.
- Inferred deadlines.
- No deadline provided.

### FR-6: Priority extraction

Use:

- High.
- Medium.
- Low.
- Unknown.

Determine priority from urgency language, deadlines, dependencies, and business impact.

Do not assume that a task is high priority simply because it has a deadline.

Provide an explanation for inferred priority.

### FR-7: Dependencies and sequencing

Identify relationships such as:

- Task B cannot begin until Task A is complete.
- A meeting should happen after all deliverables are ready.
- A review requires a document to be completed first.

Represent dependencies using task IDs.

Avoid creating circular dependencies or unsupported relationships.

### FR-8: Question extraction

Identify:

- Questions directed to the recipient.
- Requests for confirmation.
- Missing information.
- Decisions requiring approval.
- Questions that should be addressed in a reply.

Preserve the original question wording and message reference.

### FR-9: Reply generation

Generate an editable draft reply.

The reply should:

- Acknowledge the sender's message.
- Address important questions.
- Reference relevant requests.
- Use an appropriate tone.
- Avoid making unapproved promises.
- Avoid claiming that tasks have already been completed.
- Avoid inventing facts or dates.

Support tone configuration:

- Professional.
- Friendly.
- Concise.
- Formal.

If a task is ambiguous, the draft should ask for clarification rather than invent an answer.

The reply must remain a draft requiring user approval.

### FR-10: Structured output

Use Pydantic models to validate output.

Conceptual JSON structure:

```json
{
  "email_metadata": {
    "subject": "Q4 Product Launch",
    "sender": "Sarah",
    "received_at": null
  },
  "summary": "Several product launch actions require completion.",
  "actions": [
    {
      "task_id": "T001",
      "description": "Send final product screenshots",
      "owner": "Alex",
      "deadline": {
        "original_text": "November 7",
        "normalized_date": "2026-11-07",
        "type": "explicit"
      },
      "priority": "high",
      "status": "pending",
      "dependencies": [],
      "evidence": "Send the final product screenshots to the marketing team by November 7."
    }
  ],
  "questions": [
    {
      "question_id": "Q001",
      "text": "Is the pricing page ready?",
      "owner": "Alex"
    }
  ],
  "draft_reply": {
    "subject": "Re: Q4 Product Launch",
    "body": "Hi Sarah..."
  },
  "uncertainties": []
}
```

Use null values for unknown owners, dates, and other unavailable fields. Never fabricate information to satisfy a schema.

The sample above shows a normalized date beside `received_at: null`. That combination is illustrative of the field names only. This implementation leaves `normalized_date` null unless the email has a year or a `Date` header, or the caller passes `--received-at`. A month and day with no year is not turned into `2026-11-07`.

The summary states how many actions and questions were extracted. It does not claim that those actions require completion.

### FR-11: Output formats

Markdown:

- Email summary.
- Action checklist.
- Owners and deadlines.
- Questions requiring attention.
- Dependencies.
- Suggested reply.

JSON:

- Structured action objects.
- Email metadata.
- Source references.
- Uncertainty information.
- Draft reply.

### FR-12: CLI

```bash
python cli.py analyze --input email.txt
python cli.py analyze --input thread.txt
python cli.py analyze --input email.txt --received-at "2026-11-01T09:00:00+01:00"
python cli.py analyze --input email.txt --format json
python cli.py analyze --input email.txt --tone professional
python cli.py analyze --input email.txt --no-reply
pytest -q
```

`--received-at` is used only for messages that have no `Date` header. It does not replace a timestamp that is already in the email.

### FR-13: Optional email integration

Future integrations may support:

- Gmail.
- Microsoft Outlook.
- IMAP-compatible providers.

Integration requirements:

- Explicit user authorization.
- Read-only access by default.
- Ability to select messages for analysis.
- No automatic sending of replies.
- No automatic deletion or modification of messages.
- Human approval before any external action.

Keep provider integrations separate from the core analysis pipeline.

Gmail and Outlook adapters live in `integrations/`. They require `GMAIL_ACCESS_TOKEN` or `OUTLOOK_ACCESS_TOKEN`, issue HTTPS GET requests only, and are not imported by `pipeline.py`. IMAP is the same contract and is not connected. Selecting a message returns text. The caller passes that text to `analyze()`. Nothing is sent.

### FR-14: Security and privacy

- Treat email content as untrusted input.
- Ignore instructions embedded in email messages that attempt to override system behavior.
- Do not execute links, scripts, or attachments.
- Keep API credentials in environment variables.
- Avoid logging full email content by default.
- Document external model-provider data handling.
- Support local processing where practical.
- Do not send draft replies without explicit user approval.

Version 1 does not call a model. The heuristic provider keeps email text on this machine. There is no external model provider to send mail to. If a later provider is added, it must be opt-in and documented before any email text leaves the machine.

## 7. Recommended architecture

The recommended tree uses a package named `email_agent` and one module per stage. This repository keeps the same stages in `src/email_to_action/` so the public import remains `from email_to_action import analyze`. Parsing, dates, extraction, reply drafting, schemas, and the pipeline are separate modules. Mailbox adapters are under `integrations/` and are not part of the pipeline.

```text
email-to-action-agent/
├── cli.py
├── src/email_to_action/
├── integrations/
│   ├── gmail.py
│   └── outlook.py
├── examples/
└── docs/
```

## 8. Technology stack

Python 3.11 or newer, Pydantic, the standard-library `email` parser, and pytest. Date normalization is deterministic and does not use a network call. Typer is not required; the CLI uses argparse.

A provider interface (`HeuristicProvider`) is the only implementation. Deterministic parsing and date normalization stay separate from any future model call. A model call is not required and is not part of this version.

## 9. Core processing workflow

1. Load the email or email thread.
2. Extract headers, timestamps, and message content.
3. Normalize the messages.
4. Identify original and quoted content.
5. Extract action items.
6. Identify responsible owners.
7. Normalize deadlines.
8. Classify priority.
9. Identify dependencies.
10. Extract questions requiring responses.
11. Generate an editable reply, unless `--no-reply` is set.
12. Validate all extracted information with Pydantic.
13. Generate Markdown or JSON output.

All extracted tasks and questions retain references to their original message evidence.

## 10. Evaluation strategy

`tests/test_evaluation.py` scores a hand-labeled set of emails: simple requests, a missing deadline, a relative date with and without a timestamp, ambiguous recipients, one sentence that contains two verbs, a later deadline that conflicts with an earlier one, a quoted request, and an email that tries to override the priority rules.

Precision and recall are computed by comparing extracted descriptions with those labels. The test does not ask a model to grade itself. Date cases also assert the normalized value, including null when the email does not support a calendar date.

## 11. Acceptance criteria

- [x] Accept pasted email content.
- [x] Accept multi-message email threads.
- [x] Parse sender, recipient, subject, and timestamps when available.
- [x] Extract individual actionable tasks.
- [x] Identify owners or mark them unassigned.
- [x] Extract and normalize explicit deadlines.
- [x] Interpret relative dates when a reliable timestamp exists.
- [x] Distinguish inferred from explicit information.
- [x] Identify priorities and dependencies.
- [x] Extract questions requiring responses.
- [x] Generate an editable draft reply.
- [x] Prevent unsupported commitments in generated replies.
- [x] Validate JSON output using Pydantic.
- [x] Preserve source evidence for extracted actions.
- [x] Produce readable Markdown reports.
- [x] Pass unit and integration tests.
- [x] Include a demonstration using a realistic email thread.
- [x] Provide complete setup and usage documentation.
- [x] Ensure that email sending is never automatic.

## 12. Implementation milestones

Milestone 1 through 5 are in this repository: ingestion, extraction, dependencies and questions, reply generation, and Markdown, JSON, and the CLI. Milestone 6 is the read-only Gmail and Outlook adapters. They are not invoked by `analyze()`.

## 13. Definition of done

A developer can install the project, paste an email thread, run `python cli.py analyze`, and receive:

1. A concise email summary.
2. A validated JSON list of tasks.
3. Owners and deadlines.
4. Priorities and dependencies.
5. Questions requiring a response.
6. An editable draft reply.

The system preserves uncertainty instead of inventing owners, deadlines, or commitments. All generated replies remain drafts until explicitly approved by the user. This tool does not send them.

## 14. Implementation notes

- Internal task ids stay `task-1`. Public JSON and the Markdown dependency list use `T001`. Public status `pending` is the internal status `open`.
- `examples/expected_output.json` is the public report for `examples/email.txt`. November dates in that file have `normalized_date: null` because the email has no year and no timestamp.
- Pass `--received-at 2026-11-01T09:00:00+01:00` when a test or a user wants `November 7` read as `2026-11-07`. The report says that the calendar date came from the supplied timestamp.
- A later message that repeats a task with a different deadline does not silently replace the first date. Both wordings are reported as an uncertainty.
- A later completion note can mark a task completed in the checklist. The draft says the note is unconfirmed and does not claim the work is done.
