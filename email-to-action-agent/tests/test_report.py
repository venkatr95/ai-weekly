"""Markdown and JSON stay aligned with the validated action list."""

from email_to_action.pipeline import analyze
from email_to_action.report import render_json, render_markdown
from email_to_action.schemas import ActionList

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
    assert "| Complete the landing page. | Alex | November 10 | High | Open |" in markdown
    assert "| Confirm whether the pricing page is ready. | Alex | Not specified | Medium | Open |" in markdown
    assert "After other tasks" in markdown
    assert "Is the pricing page ready?" in markdown
    assert "task-5 depends on task-1, task-2, task-3, task-4." in markdown
    assert "does not by itself" in markdown
    restored = ActionList.model_validate_json(render_json(action))
    assert [task.task_id for task in restored.tasks] == [task.task_id for task in action.tasks]
    assert any(person.name == "marketing team" and person.role == "mentioned" for person in action.participants)
    assert any(person.name == "John" and person.role == "mentioned" for person in action.participants)
