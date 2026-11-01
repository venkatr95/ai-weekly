"""Validated records for an email thread and the action list derived from it."""

from __future__ import annotations

import re
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

ParticipantRole = Literal["sender", "recipient", "cc", "mentioned"]
OwnerRole = Literal["named", "recipient", "sender", "team", "unassigned"]
QuestionKind = Literal["question", "confirmation", "missing_information", "approval"]

_PROMISE = re.compile(
    r"\b(i'll|i will|we'll|we will|i commit|i promise|count on me to)\b",
    re.IGNORECASE,
)


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class EvidenceType(str, Enum):
    explicit_request = "explicit_request"
    suggested_action = "suggested_action"
    implied_action = "implied_action"
    commitment = "commitment"


class PriorityLevel(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"
    unknown = "unknown"


class DeadlineKind(str, Enum):
    explicit = "explicit"
    inferred = "inferred"
    none = "none"
    unresolved = "unresolved"


class DatePrecision(str, Enum):
    day = "day"
    time = "time"
    range = "range"
    relative = "relative"
    event = "event"
    none = "none"


class TaskStatus(str, Enum):
    open = "open"
    completed = "completed"
    blocked = "blocked"


class Participant(BaseModel):
    name: str | None = None
    email: str | None = None
    role: ParticipantRole


class Owner(BaseModel):
    name: str | None = None
    email: str | None = None
    role: OwnerRole
    confidence: Confidence
    ambiguous: bool = False


class Deadline(BaseModel):
    original_wording: str | None = None
    normalized_date: str | None = None
    time: str | None = None
    timezone: str | None = None
    precision: DatePrecision = DatePrecision.none
    confidence: Confidence = Confidence.medium
    kind: DeadlineKind = DeadlineKind.none
    source_message_id: str | None = None

    @model_validator(mode="after")
    def check_deadline(self) -> "Deadline":
        if self.kind == DeadlineKind.none and (self.original_wording or self.normalized_date):
            raise ValueError("An empty deadline cannot carry wording or a normalized date.")
        if self.kind == DeadlineKind.unresolved and self.normalized_date:
            raise ValueError("An unresolved relative date cannot have a normalized date.")
        if self.kind == DeadlineKind.inferred and not self.normalized_date:
            raise ValueError("An inferred deadline needs a normalized date.")
        if self.kind in {DeadlineKind.explicit, DeadlineKind.unresolved, DeadlineKind.inferred}:
            if not self.original_wording:
                raise ValueError("Deadline wording is required when a deadline was stated or inferred.")
        return self


class EmailMessage(BaseModel):
    message_id: str
    sender_name: str | None = None
    sender_email: str | None = None
    to: list[Participant] = Field(default_factory=list)
    cc: list[Participant] = Field(default_factory=list)
    subject: str | None = None
    date_raw: str | None = None
    date_iso: str | None = None
    body: str
    quoted_text: str = ""
    signature: str = ""
    addressee_name: str | None = None
    addressee_ambiguous: bool = False
    warnings: list[str] = Field(default_factory=list)


class Task(BaseModel):
    task_id: str
    description: str
    owner: Owner
    deadline: Deadline
    priority: PriorityLevel
    priority_explanation: str = Field(min_length=1)
    status: TaskStatus = TaskStatus.open
    dependencies: list[str] = Field(default_factory=list)
    related_questions: list[str] = Field(default_factory=list)
    message_id: str
    supporting_text: str = Field(min_length=1)
    evidence_type: EvidenceType
    confidence: Confidence


class Question(BaseModel):
    question_id: str
    text: str
    original_wording: str
    message_id: str
    directed_to: str | None = None
    kind: QuestionKind


class Commitment(BaseModel):
    commitment_id: str
    description: str
    made_by: str | None = None
    message_id: str
    supporting_text: str
    deadline: Deadline | None = None


class DraftReply(BaseModel):
    subject: str | None = None
    body: str = Field(min_length=1)
    tone: str = "professional"
    accepts_commitments: bool = False
    notes: list[str] = Field(default_factory=list)


class ActionList(BaseModel):
    subject: str | None = None
    participants: list[Participant] = Field(default_factory=list)
    messages: list[EmailMessage] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)
    commitments: list[Commitment] = Field(default_factory=list)
    draft_reply: DraftReply
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_action_list(self) -> "ActionList":
        if self.draft_reply.accepts_commitments:
            raise ValueError("Draft reply must not accept commitments.")
        if _PROMISE.search(self.draft_reply.body):
            raise ValueError("Draft reply contains an unapproved commitment.")

        task_ids = [task.task_id for task in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("Task ids must be unique.")
        question_ids = [question.question_id for question in self.questions]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("Question ids must be unique.")
        known_questions = set(question_ids)
        known_tasks = set(task_ids)
        graph = {task.task_id: list(task.dependencies) for task in self.tasks}
        for task in self.tasks:
            if task.message_id not in {message.message_id for message in self.messages}:
                raise ValueError(f"{task.task_id} references an unknown message.")
            if task.supporting_text not in _message_text(self.messages, task.message_id):
                raise ValueError(f"{task.task_id} supporting text is not in the source message.")
            for dependency in task.dependencies:
                if dependency not in known_tasks:
                    raise ValueError(f"{task.task_id} depends on unknown task {dependency}.")
                if dependency == task.task_id:
                    raise ValueError(f"{task.task_id} cannot depend on itself.")
            for question_id in task.related_questions:
                if question_id not in known_questions:
                    raise ValueError(f"{task.task_id} references unknown question {question_id}.")
        if _has_cycle(graph):
            raise ValueError("Task dependencies contain a cycle.")
        for question in self.questions:
            source = _message_text(self.messages, question.message_id)
            if question.original_wording not in source:
                raise ValueError(f"{question.question_id} wording is not in the source message.")
        return self


def _message_text(messages: list[EmailMessage], message_id: str) -> str:
    for message in messages:
        if message.message_id == message_id:
            return message.body
    return ""


def _has_cycle(graph: dict[str, list[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for nxt in graph.get(node, []):
            if visit(nxt):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in graph)
