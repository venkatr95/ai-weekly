"""Schema rules that keep an action list safe to hand to another system."""

import pytest
from pydantic import ValidationError

from email_to_action.schemas import (
    ActionList,
    Confidence,
    DatePrecision,
    Deadline,
    DeadlineKind,
    DraftReply,
    EmailMessage,
    EvidenceType,
    Owner,
    PriorityLevel,
    Task,
)


def _message() -> EmailMessage:
    return EmailMessage(message_id="message-1", body="Please send the report by Friday.")


def _task(**overrides) -> Task:
    payload = dict(
        task_id="task-1",
        description="Send the report.",
        owner=Owner(name="Alex", role="recipient", confidence=Confidence.high, ambiguous=False),
        deadline=Deadline(
            original_wording="Friday",
            kind=DeadlineKind.unresolved,
            precision=DatePrecision.relative,
            confidence=Confidence.low,
            source_message_id="message-1",
        ),
        priority=PriorityLevel.medium,
        priority_explanation="Explicit request without urgency language.",
        message_id="message-1",
        supporting_text="Please send the report by Friday.",
        evidence_type=EvidenceType.explicit_request,
        confidence=Confidence.high,
    )
    payload.update(overrides)
    return Task(**payload)


def _action(tasks: list[Task], reply: str = "Thanks for the note. I have not accepted these requests.") -> ActionList:
    return ActionList(
        messages=[_message()],
        tasks=tasks,
        draft_reply=DraftReply(body=reply, accepts_commitments=False),
    )


def test_valid_action_list_passes():
    action = _action([_task()])
    assert action.tasks[0].task_id == "task-1"
    assert action.draft_reply.accepts_commitments is False


def test_reply_cannot_promise_the_work():
    with pytest.raises(ValidationError):
        _action([_task()], reply="I'll send the report by Friday.")


def test_reply_cannot_flag_itself_as_accepting_commitments():
    with pytest.raises(ValidationError):
        ActionList(
            messages=[_message()],
            tasks=[_task()],
            draft_reply=DraftReply(body="Noted.", accepts_commitments=True),
        )


def test_cycle_and_unknown_dependency_are_rejected():
    first = _task(task_id="task-1", dependencies=["task-2"])
    second = _task(
        task_id="task-2",
        description="Review the report.",
        supporting_text="Please send the report by Friday.",
        dependencies=["task-1"],
    )
    with pytest.raises(ValidationError):
        _action([first, second])

    with pytest.raises(ValidationError):
        _action([_task(dependencies=["task-9"])])


def test_unresolved_deadline_cannot_invent_a_calendar_date():
    with pytest.raises(ValidationError):
        Deadline(
            original_wording="Friday",
            normalized_date="2026-11-06",
            kind=DeadlineKind.unresolved,
            precision=DatePrecision.relative,
            source_message_id="message-1",
        )


def test_supporting_text_must_come_from_the_message():
    with pytest.raises(ValidationError):
        _action([_task(supporting_text="This sentence was not in the email.")])
