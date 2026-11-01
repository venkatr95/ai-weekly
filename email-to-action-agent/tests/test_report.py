"""Markdown and JSON stay aligned with the validated action list."""

from email_to_action.pipeline import analyze
from email_to_action.report import render_json, render_markdown
from email_to_action.schemas import PublicReport

LAUNCH = """\
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
"""


def test_markdown_summary_and_json_round_trip():
    action = analyze(LAUNCH)
    markdown = render_markdown(action)
    assert "| Complete the landing page. | Alex | November 10 | High | Pending |" in markdown
    assert "| Confirm whether the pricing page is ready. | Alex | Not specified | Medium | Pending |" in markdown
    assert "After other tasks" in markdown
    assert "Is the pricing page ready?" in markdown
    assert "T005 depends on T001, T002, T003, T004." in markdown
    assert "does not by itself" in markdown
    assert 'Extracted 5 actions and 1 question from "Q4 Product Launch".' in markdown
    restored = PublicReport.model_validate_json(render_json(action))
    assert [item.task_id for item in restored.actions] == ["T001", "T002", "T003", "T004", "T005"]
    assert restored.actions[1].deadline is not None
    assert restored.actions[1].deadline.normalized_date is None
    assert restored.actions[1].deadline.original_text == "November 7"
    assert restored.actions[-1].owner is None
    assert restored.questions[0].question_id == "Q001"
    assert restored.email_metadata.received_at is None
    assert any("no year" in item or "not a calendar date" in item for item in restored.uncertainties)
    assert any(person.name == "marketing team" and person.role == "mentioned" for person in action.participants)
    assert any(person.name == "John" and person.role == "mentioned" for person in action.participants)
