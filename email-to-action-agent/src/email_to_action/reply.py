"""Draft a reply that acknowledges requests without accepting them."""

from __future__ import annotations

from email_to_action.errors import EmailActionError
from email_to_action.schemas import (
    Commitment,
    DatePrecision,
    DeadlineKind,
    DraftReply,
    EmailMessage,
    Question,
    Task,
    TaskStatus,
    ToneName,
)
from email_to_action.textutil import first_name

_TONES = {"professional", "friendly", "concise", "formal"}
_DATED = {DatePrecision.day, DatePrecision.time, DatePrecision.range}


def build_reply(
    messages: list[EmailMessage],
    tasks: list[Task],
    questions: list[Question],
    commitments: list[Commitment],
    tone: str = "professional",
) -> DraftReply:
    selected = _tone(tone)
    latest = messages[-1] if messages else None
    sender = first_name(latest.sender_name) if latest and latest.sender_name else "there"
    by_id = {message.message_id: message for message in messages}
    lines = [_greeting(selected, sender), "", _opening(selected)]
    if tasks:
        lines.extend(["", _requests_heading(selected)])
        for task in tasks:
            owner = task.owner.name or "Unassigned"
            when = task.deadline.original_wording or "not specified"
            lines.append(f"- {task.description} Owner: {owner}. Deadline: {when}.")
    else:
        lines.extend(["", _empty(selected)])
    clarifications = _clarifications(tasks, by_id)
    if clarifications:
        lines.extend(["", _clarify_heading(selected)])
        lines.extend(f"- {item}" for item in clarifications)
    if questions:
        lines.extend(["", "Questions that still need a response:"])
        for question in questions:
            lines.append(f"- {question.text}")
    if commitments:
        lines.extend(["", "Commitments already stated in the thread:"])
        for item in commitments:
            who = item.made_by or "A participant"
            lines.append(f"- {who} committed to: {item.description}")
    if any(task.status == TaskStatus.completed for task in tasks):
        lines.extend(["", _completion_note()])
    lines.extend(["", _closing(selected), "", _signoff(selected), _signature_name(latest)])
    return DraftReply(
        subject=_reply_subject(messages),
        body="\n".join(lines),
        tone=selected,
        accepts_commitments=False,
        requires_approval=True,
        notes=[
            "The draft acknowledges requests and does not promise to complete them.",
            "Deadlines are quoted from the email and are not accepted by the draft.",
            "Ambiguous owners and dates are asked about instead of being filled in.",
            "The draft does not claim that a task is already complete.",
            "Sending requires explicit approval. This tool does not send email.",
        ],
    )


def _tone(tone: str) -> ToneName:
    if tone not in _TONES:
        raise EmailActionError("tone must be professional, friendly, concise, or formal.")
    return tone  # type: ignore[return-value]


def _greeting(tone: ToneName, sender: str) -> str:
    if tone == "formal":
        if sender == "there":
            return "Hello,"
        return f"Dear {sender},"
    return f"Hi {sender},"


def _opening(tone: ToneName) -> str:
    if tone == "friendly":
        return "Thanks for writing. I listed the requests below so they are easy to review. None of them is a commitment."
    if tone == "concise":
        return "Noted. The items below are not commitments."
    if tone == "formal":
        return "Thank you for your message. The items below are recorded for review. This draft does not accept them as commitments."
    return "Thanks for the note. I have listed what I found below, and I have not accepted any of it as a commitment."


def _requests_heading(tone: ToneName) -> str:
    if tone == "friendly":
        return "Here is what I found:"
    if tone == "concise":
        return "Requests:"
    if tone == "formal":
        return "Requests:"
    return "Requests mentioned:"


def _empty(tone: ToneName) -> str:
    if tone == "concise":
        return "No request to track."
    if tone == "formal":
        return "No request was found to track."
    return "I did not find a request to track."


def _clarify_heading(tone: ToneName) -> str:
    if tone == "friendly":
        return "Could you clarify these points?"
    if tone == "concise":
        return "Please clarify:"
    if tone == "formal":
        return "Clarification is requested for the following:"
    return "These points are ambiguous, so this draft asks rather than guessing:"


def _closing(tone: ToneName) -> str:
    if tone == "friendly":
        return "Edit anything that looks off. This stays a draft until you approve it, and it does not confirm dates or owners."
    if tone == "concise":
        return "Draft only. Approve it before sending. Dates and owners are not confirmed."
    if tone == "formal":
        return "This reply remains a draft until it is approved. It does not confirm dates, owners, or next steps."
    return (
        "This draft can be edited before anything is sent. "
        "It does not confirm dates, owners, or next steps on your behalf. "
        "It remains a draft until you approve it."
    )


def _signoff(tone: ToneName) -> str:
    if tone == "formal":
        return "Sincerely,"
    return "Best,"


def _completion_note() -> str:
    return (
        "A later note in the thread may indicate that a request is complete. "
        "This draft does not confirm completion."
    )


def _clarifications(tasks: list[Task], messages: dict[str, EmailMessage]) -> list[str]:
    items: list[str] = []
    for task in tasks:
        if task.owner.ambiguous or not task.owner.name:
            items.append(f'Who should own "{task.description}"?')
        wording = task.deadline.original_wording or "the stated date"
        message = messages.get(task.message_id)
        supplied = message is not None and not message.date_iso
        if task.deadline.kind == DeadlineKind.unresolved:
            items.append(
                f'The deadline "{wording}" cannot be placed on a calendar without a message timestamp. '
                "What date should be used?"
            )
        elif task.deadline.kind == DeadlineKind.inferred and task.deadline.normalized_date:
            items.append(
                f'The deadline "{wording}" was inferred as {task.deadline.normalized_date}. Please confirm that date.'
            )
        elif (
            task.deadline.kind == DeadlineKind.explicit
            and task.deadline.normalized_date
            and supplied
        ):
            items.append(
                f'The deadline "{wording}" is normalized to {task.deadline.normalized_date} '
                "only because a received-at timestamp was supplied. "
                "The email itself does not state that calendar date. Please confirm it."
            )
        elif (
            task.deadline.kind == DeadlineKind.explicit
            and task.deadline.normalized_date is None
            and task.deadline.precision in _DATED
        ):
            items.append(
                f'The deadline "{wording}" has no year in the email, so no calendar date is assigned. Which year applies?'
            )
    return items


def _signature_name(message: EmailMessage | None) -> str:
    if message and message.addressee_name:
        return message.addressee_name
    return "[Your name]"


def _reply_subject(messages: list[EmailMessage]) -> str | None:
    subject = next((message.subject for message in reversed(messages) if message.subject), None)
    if not subject:
        return None
    if subject.lower().startswith("re:"):
        return subject
    return f"Re: {subject}"
