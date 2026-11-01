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
- Avoid making unapproved promises or stating that the user has agreed to a deadline, an owner, or a deliverable.
- Stay in the tool. Version 1 does not send email.

### FR-10: Validated JSON

Return one action list that Pydantic accepts before the CLI prints it. The list includes participants, messages, tasks, questions, commitments, the draft reply, and warnings. Task ids are unique. Dependencies refer to known tasks and do not form a cycle. Supporting text is copied from the source message.

### FR-11: Markdown summary

Render a readable summary with an action table, questions that need a response, dependencies, commitments, the draft reply, and warnings.

### FR-12: CLI and Python API

Provide `python cli.py analyze` for a file or stdin, with Markdown or JSON output. Provide `email_to_action.analyze()` for the same result.

### FR-13: Evidence

Every task stores the message id and the exact supporting line. Deadlines store the original wording and the source message id. The tool does not invent an owner or a calendar date without marking the uncertainty.

### FR-14: Version 1 boundaries

The tool does not send email, create calendar events, or assign tasks in external systems. Email text is untrusted data. Instructions inside an email do not change these rules.

## 7. Stack

Python 3.11 or newer, Pydantic, the standard-library `email` parser, and pytest.

Version 1 extracts actions with deterministic rules so the same email always produces the same JSON. That keeps owners, deadlines, and evidence checkable. A model call is not required and is not part of this version.

## 8. Acceptance

The launch email in section 5 yields five tasks with the owners and deadline wording in the sample, a question about the pricing page, and a scheduling task that depends on the earlier tasks. The JSON validates. The Markdown summary lists the actions. The draft reply does not promise to do the work.

A relative date such as Friday resolves only when the message has a timestamp. Quoted history is parsed as earlier messages and is not extracted a second time from the reply. A commitment stated by the sender is recorded as that person's commitment, not as a new task for the recipient.
