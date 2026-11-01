# Troubleshooting

## The Friday deadline is unresolved

The message has no `Date` or `Sent` header, and `--received-at` was not passed. Add the timestamp from the mailbox, or run:

```bash
python cli.py analyze --input email.txt --received-at "2026-11-01T09:00:00+01:00"
```

The agent does not guess a calendar date for "Friday", "tomorrow", or "next week" without that anchor. A supplied timestamp is labeled as supplied. It does not overwrite a `Date` header that is already on the message.

## `--received-at` is rejected

The value must be ISO-8601, such as `2026-11-01T09:00:00+01:00`. `next Friday` is not accepted.

## A month and day have no year

`November 10` stays as wording when the email itself has no year and no timestamp. Add a `Date` header when you want `2026-11-10`.

## An owner is unassigned

The request did not name a person, or `To` lists more than one person and the greeting does not select one. "Let's schedule a meeting" stays unassigned on purpose. The sender is the person who asked, not the person who has to do the work.

## A quoted request is missing

Quote lines that are only `>` text, with no headers and no "wrote:" line, are kept out of the new message. Paste the earlier message with its `From` header, or keep the `Original Message` separator, when that request is still open.

## The draft does not say "I will"

That is the version 1 rule. The sample reply in the PRD is illustrative and would accept work the reader has not confirmed. The draft asks when an owner or a year is missing. Edit it yourself before sending it. This tool does not send it.

`--tone professional`, `friendly`, `concise`, and `formal` change the wording. They do not change the rule. `--no-reply` omits the draft.

## The checklist says completed and the draft does not

A later message can mark an earlier request completed or blocked. The checklist shows that extraction. The draft says the note is unconfirmed and does not say the work is already done.

## `python` is not recognized

Use `py -3 cli.py analyze --input examples/launch_thread.txt`.
