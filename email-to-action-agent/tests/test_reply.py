"""The draft reply quotes requests and does not accept them."""

import re

from email_to_action.pipeline import analyze

LAUNCH = """\
From: Sarah
Subject: Q4 Product Launch

Hi Alex,

We need to finalize the product launch materials.

Could you please:
- Complete the landing page by November 10.
- Send the final product screenshots to the marketing team by November 7.

Thanks,
Sarah
"""


def test_reply_names_the_sender_and_does_not_promise():
    action = analyze(LAUNCH)
    body = action.draft_reply.body
    assert body.startswith("Hi Sarah,")
    assert body.rstrip().endswith("Alex")
    assert "landing page" in body.lower()
    assert action.draft_reply.subject == "Re: Q4 Product Launch"
    assert action.draft_reply.accepts_commitments is False
    assert re.search(r"\b(i'll|i will|we'll|we will)\b", body, re.IGNORECASE) is None
    assert "not accepted" in body.lower()


def test_reply_without_requests_does_not_invent_work():
    action = analyze("From: Sarah\n\nHi Alex,\n\nThe launch moved to December.\n\nThanks,\nSarah\n")
    assert action.tasks == []
    assert "did not find a request" in action.draft_reply.body
