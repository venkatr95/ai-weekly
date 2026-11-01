"""Draft a reply that acknowledges requests without accepting them."""

from __future__ import annotations

from email_to_action.schemas import Commitment, DraftReply, EmailMessage, Question, Task
from email_to_action.textutil import first_name


def build_reply(
    messages: list[EmailMessage],
    tasks: list[Task],
    questions: list[Question],
    commitments: list[Commitment],
) -> DraftReply:
    latest = messages[-1] if messages else None
    sender = first_name(latest.sender_name) if latest and latest.sender_name else "there"
    signature = _signature_name(latest)
    subject = _reply_subject(messages)
    lines = [
        f"Hi {sender},",
        "",
        "Thanks for the note. I have listed what I found below, and I have not accepted any of it as a commitment.",
    ]
    if tasks:
        lines.extend(["", "Requests mentioned:"])
        for task in tasks:
            owner = task.owner.name or "Unassigned"
            when = task.deadline.original_wording or "not specified"
            lines.append(f"- {task.description} Owner: {owner}. Deadline: {when}.")
    else:
        lines.extend(["", "I did not find a request to track."])
    if questions:
        lines.extend(["", "Questions that still need a response:"])
        for question in questions:
            lines.append(f"- {question.text}")
    if commitments:
        lines.extend(["", "Commitments already stated in the thread:"])
        for item in commitments:
            who = item.made_by or "A participant"
            lines.append(f"- {who} committed to: {item.description}")
    lines.extend(
        [
            "",
            "This draft can be edited before anything is sent. It does not confirm dates, owners, or next steps on your behalf.",
            "",
            "Best,",
            signature,
        ]
    )
    return DraftReply(
        subject=subject,
        body="\n".join(lines),
        tone="professional",
        accepts_commitments=False,
        notes=[
            "The draft acknowledges requests and does not promise to complete them.",
            "Deadlines are quoted from the email and are not accepted by the draft.",
        ],
    )


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
