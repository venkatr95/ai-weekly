# Architecture

The agent is a straight pipeline. Each stage returns structured records, and the last stage validates the whole action list before it is returned.

```
text or .eml
    -> parser
    -> extractor
    -> reply
    -> ActionList validation
    -> Markdown or JSON
```

## Parser

`parser.py` accepts plain text and `.eml` files. `.eml` bodies use the standard-library email parser. HTML-only bodies are converted to text and a warning is recorded.

A thread is split on `Original Message`, `Forwarded message`, and `On ... wrote:` lines. Quoted blocks that still contain headers are lifted into earlier messages. Messages with timestamps are ordered oldest first. The body then drops the signature, a trailing disclaimer, and leftover `>` quote lines. Those quote lines are stored and are not mined for new tasks.

A greeting such as "Hi Alex" supplies the addressee when `To` is missing. A first name matches a longer `To` name. Several recipients, with no greeting that selects one of them, stay ambiguous.

## Dates

`dates.py` separates a deadline phrase from the task sentence. Explicit calendar dates, weekdays, ranges, clock times, and event phrases such as "once these items are complete" are recognized.

The message timestamp is the only anchor for "Friday", "tomorrow", or "in 3 days". Without a timestamp those phrases are `unresolved` and have no normalized date. A month and day without a year uses the message year. A month that would fall more than 30 days before the message rolls into the next year. Ambiguous numeric dates such as `02/03/2026` are kept as wording only.

"The day before the review" becomes an inferred date only when one other task has a normalized day that the phrase matches.

## Extractor

`extractor.py` walks each message's new body. It reads direct requests, named requests ("John, please"), bullet lists under "Could you please", suggestions ("let's", "we should"), implied needs, and commitments ("I'll send").

The sender of a request is not the owner. "You" means the addressee. A suggestion stays unassigned. A team name such as Marketing stays a team. Commitments are stored on the sender and are not assigned to the recipient.

Priority uses urgency wording. A deadline does not by itself raise priority. "We need to finalize" before a dated explicit request can make that request high, and the explanation quotes the phrase. "When you have time" stays low. "Not urgent" does not count as urgent.

Dependencies use task ids. "Once these items are complete" depends on the earlier tasks in that message. A phrase that matches several tasks does not invent a link. Cycles are removed.

A later message can mark an earlier task completed or blocked when the sentence names that task. The same message cannot complete its own request.

## Reply and report

`reply.py` writes a draft to the latest sender and signs it with the addressee when that person is known. The tone is professional, friendly, concise, or formal. Ambiguous owners and dates become questions in the draft. A task marked completed is described as unconfirmed. The validator rejects a draft that promises the work, claims it is already done, or sets `accepts_commitments` to true.

`report.py` renders the email summary, checklist, owners, questions, dependencies, and the draft. `render_json` validates a public report: metadata, summary, `T001` actions, questions, uncertainties, source lines, and the draft. An open task is `pending` in that JSON. A missing owner or a missing calendar date is null.

`--received-at` is passed into the extractor as a fallback clock. Messages that already have `date_iso` keep that clock.

## Integrations

`integrations/gmail.py` and `integrations/outlook.py` list and read messages over HTTPS GET. The pipeline does not import them. They require an access token and have no send or delete method.

## What version 1 does not do

It does not send mail, create calendar events, or call a model. `providers.py` exposes `HeuristicProvider` as the only extractor. Email text is data. Instructions inside the email do not change these rules.
