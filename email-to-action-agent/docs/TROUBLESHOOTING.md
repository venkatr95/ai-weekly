# Troubleshooting

## The Friday deadline is unresolved

The message has no `Date` or `Sent` header. Add the timestamp from the mailbox and run the command again. The agent does not guess a calendar date for "Friday", "tomorrow", or "next week" without that anchor.

## A month and day have no year

`November 10` stays as wording when the email itself has no year and no timestamp. Add a `Date` header when you want `2026-11-10`.

## An owner is unassigned

The request did not name a person, or `To` lists more than one person and the greeting does not select one. "Let's schedule a meeting" stays unassigned on purpose. The sender is the person who asked, not the person who has to do the work.

## A quoted request is missing

Quote lines that are only `>` text, with no headers and no "wrote:" line, are kept out of the new message. Paste the earlier message with its `From` header, or keep the `Original Message` separator, when that request is still open.

## The draft does not say "I will"

That is the version 1 rule. The sample reply in the PRD is illustrative and would accept work the reader has not confirmed. Edit the draft yourself before sending it. This tool does not send it.

## `python` is not recognized

Use `py -3 cli.py analyze --input examples/launch_thread.txt`.
