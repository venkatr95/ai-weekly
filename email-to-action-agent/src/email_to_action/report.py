"""Markdown and JSON renderings of a validated action list."""

from __future__ import annotations

import json
import re

from email_to_action.schemas import (
    ActionList,
    DatePrecision,
    Deadline,
    DeadlineKind,
    EmailMetadata,
    Owner,
    PublicAction,
    PublicDeadline,
    PublicDraft,
    PublicQuestion,
    PublicReport,
    SourceReference,
    Task,
    TaskStatus,
)


def render_json(action: ActionList) -> str:
    return json.dumps(to_public(action).model_dump(mode="json"), indent=2, ensure_ascii=False)


def render_markdown(action: ActionList) -> str:
    lines = ["# Action summary", "", "## Email summary", "", build_summary(action), ""]
    if action.subject:
        lines.append(f"**Subject:** {action.subject}")
    if action.participants:
        rendered = ", ".join(_participant(person.name, person.email, person.role) for person in action.participants)
        lines.append(f"**Participants:** {rendered}")
    lines.extend(["", "## Action checklist", "", "| Task | Owner | Deadline | Priority | Status |", "| --- | --- | --- | --- | --- |"])
    if not action.tasks:
        lines.append("| No open requests | Unassigned | Not specified | Unknown | Pending |")
    for task in action.tasks:
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(task.description),
                    _cell(_owner_label(task.owner)),
                    _cell(_deadline_label(task.deadline)),
                    _cell(task.priority.value.title()),
                    _cell(_status_label(task.status)),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Owners and deadlines", ""])
    if action.tasks:
        for task in action.tasks:
            lines.append(
                f"- {_public_task_id(task.task_id)}: {_owner_label(task.owner)}. {_deadline_label(task.deadline)}."
            )
    else:
        lines.append("None.")
    lines.extend(["", "## Questions requiring attention", ""])
    if action.questions:
        lines.extend(f"- {question.text}" for question in action.questions)
    else:
        lines.append("None.")
    lines.extend(["", "## Dependencies", ""])
    linked = [task for task in action.tasks if task.dependencies]
    if linked:
        for task in linked:
            deps = ", ".join(_public_task_id(item) for item in task.dependencies)
            lines.append(f"- {_public_task_id(task.task_id)} depends on {deps}.")
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
        lines.extend(f"- {_public_task_id(task.task_id)}: {task.priority_explanation}" for task in action.tasks)
    else:
        lines.append("None.")
    lines.extend(["", "## Suggested reply", ""])
    if action.draft_reply is None:
        lines.append("No reply was requested. A reply is never sent without explicit approval.")
    else:
        if action.draft_reply.subject:
            lines.append(f"**Subject:** {action.draft_reply.subject}")
            lines.append("")
        lines.append(action.draft_reply.body)
        lines.extend(["", "This reply is a draft and is not sent."])
    uncertainties = build_uncertainties(action)
    lines.extend(["", "## Uncertainties", ""])
    if uncertainties:
        lines.extend(f"- {item}" for item in uncertainties)
    else:
        lines.append("None.")
    lines.append("")
    return "\n".join(lines).rstrip()


def to_public(action: ActionList) -> PublicReport:
    id_map = {task.task_id: _public_task_id(task.task_id) for task in action.tasks}
    question_map = {question.question_id: _public_question_id(question.question_id) for question in action.questions}
    actions = [_public_action(task, id_map) for task in action.tasks]
    questions = [
        PublicQuestion(
            question_id=question_map[question.question_id],
            text=question.text,
            owner=question.directed_to,
            message_id=question.message_id,
            evidence=question.original_wording,
        )
        for question in action.questions
    ]
    draft = None
    if action.draft_reply is not None:
        draft = PublicDraft(
            subject=action.draft_reply.subject,
            body=action.draft_reply.body,
            tone=action.draft_reply.tone,
            requires_approval=True,
            accepts_commitments=False,
        )
    return PublicReport(
        email_metadata=EmailMetadata(
            subject=action.subject,
            sender=_sender(action),
            received_at=_received_at(action),
        ),
        summary=build_summary(action),
        actions=actions,
        questions=questions,
        draft_reply=draft,
        uncertainties=build_uncertainties(action),
        source_references=_sources(action),
        requires_approval=True,
    )


def build_summary(action: ActionList) -> str:
    subject = action.subject or "the message"
    task_count = len(action.tasks)
    question_count = len(action.questions)
    if task_count == 0 and question_count == 0:
        return f'No actions or questions were extracted from "{subject}".'
    parts: list[str] = []
    if task_count:
        parts.append(f"{task_count} action" + ("s" if task_count != 1 else ""))
    if question_count:
        parts.append(f"{question_count} question" + ("s" if question_count != 1 else ""))
    joined = " and ".join(parts)
    return (
        f'Extracted {joined} from "{subject}". '
        "Owners and dates are included only when the email states them."
    )


def build_uncertainties(action: ActionList) -> list[str]:
    items: list[str] = []
    dated = {DatePrecision.day, DatePrecision.time, DatePrecision.range}
    for task in action.tasks:
        public_id = _public_task_id(task.task_id)
        if task.owner.ambiguous:
            items.append(f"{public_id} owner is ambiguous.")
        elif not task.owner.name:
            items.append(f"{public_id} has no owner.")
        wording = task.deadline.original_wording
        if task.deadline.kind == DeadlineKind.unresolved and wording:
            items.append(f'{public_id} deadline "{wording}" is unresolved because the message has no timestamp.')
        elif task.deadline.kind == DeadlineKind.inferred and task.deadline.normalized_date:
            items.append(
                f'{public_id} deadline "{wording}" was inferred as {task.deadline.normalized_date} and should be confirmed.'
            )
        elif (
            task.deadline.kind == DeadlineKind.explicit
            and task.deadline.normalized_date is None
            and task.deadline.precision in dated
            and wording
        ):
            items.append(
                f'{public_id} deadline "{wording}" is not a calendar date because the email does not include a year or a timestamp.'
            )
        if task.status == TaskStatus.completed:
            items.append(f"{public_id} is marked completed from a later message. Confirm that before treating it as done.")
        elif task.status == TaskStatus.blocked:
            items.append(f"{public_id} is marked blocked from a later message. Confirm that before treating it as settled.")
    for warning in action.warnings:
        public = _publicize(warning)
        if public not in items:
            items.append(public)
    return items


def _public_action(task: Task, id_map: dict[str, str]) -> PublicAction:
    deadline = None
    if task.deadline.kind != DeadlineKind.none:
        deadline = PublicDeadline(
            original_text=task.deadline.original_wording,
            normalized_date=task.deadline.normalized_date,
            type=task.deadline.kind.value,
            time=task.deadline.time,
            timezone=task.deadline.timezone,
            precision=task.deadline.precision.value,
            confidence=task.deadline.confidence.value,
        )
    status = "pending" if task.status == TaskStatus.open else task.status.value
    return PublicAction(
        task_id=id_map[task.task_id],
        description=task.description,
        owner=task.owner.name,
        deadline=deadline,
        priority=task.priority.value,
        status=status,
        dependencies=[id_map[item] for item in task.dependencies],
        evidence=task.supporting_text,
        message_id=task.message_id,
        priority_explanation=task.priority_explanation,
        evidence_type=task.evidence_type.value,
        confidence=task.confidence.value,
    )


def _sources(action: ActionList) -> list[SourceReference]:
    evidence: dict[str, list[str]] = {message.message_id: [] for message in action.messages}
    for task in action.tasks:
        bucket = evidence.setdefault(task.message_id, [])
        if task.supporting_text not in bucket:
            bucket.append(task.supporting_text)
    for question in action.questions:
        bucket = evidence.setdefault(question.message_id, [])
        if question.original_wording not in bucket:
            bucket.append(question.original_wording)
    return [
        SourceReference(
            message_id=message.message_id,
            sender=message.sender_name,
            subject=message.subject,
            date=message.date_iso,
            evidence=evidence.get(message.message_id, []),
        )
        for message in action.messages
    ]


def _sender(action: ActionList) -> str | None:
    for message in reversed(action.messages):
        if message.sender_name or message.sender_email:
            return message.sender_name or message.sender_email
    return None


def _received_at(action: ActionList) -> str | None:
    for message in reversed(action.messages):
        if message.date_iso:
            return message.date_iso
    return action.reference_timestamp


def _public_task_id(task_id: str) -> str:
    match = re.fullmatch(r"task-(\d+)", task_id)
    if match:
        return f"T{int(match.group(1)):03d}"
    return task_id


def _public_question_id(question_id: str) -> str:
    match = re.fullmatch(r"question-(\d+)", question_id)
    if match:
        return f"Q{int(match.group(1)):03d}"
    return question_id


def _publicize(text: str) -> str:
    text = re.sub(r"\btask-(\d+)\b", lambda match: f"T{int(match.group(1)):03d}", text)
    return re.sub(r"\bquestion-(\d+)\b", lambda match: f"Q{int(match.group(1)):03d}", text)


def _status_label(status: TaskStatus) -> str:
    if status == TaskStatus.open:
        return "Pending"
    return status.value.replace("_", " ").title()


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
