"""The draft reply quotes requests and does not accept them."""

import re
from pathlib import Path

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


def test_ambiguous_dates_and_owners_are_questions():
    action = analyze(Path(__file__).resolve().parents[1] / "examples" / "launch_thread.txt")
    body = action.draft_reply.body
    assert "Who should own" in body
    assert "Schedule a final review meeting" in body
    assert "Which year applies?" in body
    assert "2026" not in body
    assert "approve" in body.lower()


def test_tones_do_not_promise_or_claim_completion():
    for tone in ("professional", "friendly", "concise", "formal"):
        action = analyze(LAUNCH, tone=tone)
        body = action.draft_reply.body.lower()
        assert action.draft_reply.tone == tone
        assert "i'll" not in body
        assert "i will" not in body
        assert "already sent" not in body
        assert "already completed" not in body
        assert "approve" in body


def test_completed_status_is_not_claimed_in_the_reply():
    thread = """\
From: Sarah
To: Alex
Date: Mon, 02 Nov 2026 09:00:00 -0500
Subject: Screenshots

Hi Alex,

Please send the screenshots by Friday.

From: Sarah
To: Alex
Date: Tue, 03 Nov 2026 09:00:00 -0500
Subject: Re: Screenshots

Hi Alex,

The screenshots went out yesterday.
"""
    action = analyze(thread)
    assert action.tasks[0].status.value == "completed"
    body = action.draft_reply.body.lower()
    assert "does not confirm completion" in body
    assert "already sent" not in body
    assert "i completed" not in body
