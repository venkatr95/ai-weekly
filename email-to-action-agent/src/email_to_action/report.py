"""Markdown and JSON renderings of a validated action list."""

from __future__ import annotations

import json
import re

from email_to_action.schemas import ActionList, Deadline, DeadlineKind, Owner, Task


def render_json(action: ActionList) -> str:
    return json.dumps(action.model_dump(mode="json"), indent=2, ensure_ascii=False)


def render_markdown(action: ActionList) -> str:
    lines = ["# Action summary", ""]
    if action.subject:
        lines.append(f"**Subject:** {action.subject}")
    if action.participants:
        rendered = ", ".join(_participant(person.name, person.email, person.role) for person in action.participants)
        lines.append(f"**Participants:** {rendered}")
    lines.extend(["", "| Task | Owner | Deadline | Priority | Status |", "| --- | --- | --- | --- | --- |"])
    if not action.tasks:
        lines.append("| No open requests | Unassigned | Not specified | Unknown | Open |")
    for task in action.tasks:
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(task.description),
                    _cell(_owner_label(task.owner)),
                    _cell(_deadline_label(task.deadline)),
                    _cell(task.priority.value.title()),
                    _cell(task.status.value.replace("_", " ").title()),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Questions requiring a response", ""])
    if action.questions:
        lines.extend(f"- {question.text}" for question in action.questions)
    else:
        lines.append("None.")
    lines.extend(["", "## Dependencies", ""])
    linked = [task for task in action.tasks if task.dependencies]
    if linked:
        for task in linked:
            lines.append(f"- {task.task_id} depends on {', '.join(task.dependencies)}.")
    else:
        lines.append("None.")
    lines.extend(["", "## Commitments", ""])
    if action.commitments:
        for item in action.commitments:
            when = item.deadline.original_wording if item.deadline and item.deadline.original_wording else "not specified"
            lines.append(f"- {item.made_by or 'A participant'}: {item.description} Deadline: {when}.")
    else:
        lines.append("None.")
    lines.extend(["", "## Priority notes", ""])
    if action.tasks:
        lines.extend(f"- {task.task_id}: {task.priority_explanation}" for task in action.tasks)
    else:
        lines.append("None.")
    lines.extend(["", "## Suggested reply", ""])
    if action.draft_reply.subject:
        lines.append(f"**Subject:** {action.draft_reply.subject}")
        lines.append("")
    lines.append(action.draft_reply.body)
    if action.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in action.warnings)
    lines.append("")
    return "\n".join(lines).rstrip()


def _deadline_label(deadline: Deadline) -> str:
    if deadline.kind == DeadlineKind.none:
        return "Not specified"
    wording = deadline.original_wording or "Not specified"
    if deadline.kind == DeadlineKind.unresolved:
        return f"{wording} (unresolved)"
    if deadline.precision.value == "event" and re.search(r"\b(these|those|remaining|other)\b", wording, re.IGNORECASE):
        return "After other tasks"
    return wording


def _owner_label(owner: Owner) -> str:
    if owner.name:
        return owner.name
    return "Unassigned"


def _participant(name: str | None, email: str | None, role: str) -> str:
    label = name or email or "Unknown"
    if name and email:
        label = f"{name} <{email}>"
    return f"{label} ({role})"


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def task_rows(action: ActionList) -> list[Task]:
    return list(action.tasks)
