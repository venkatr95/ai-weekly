"""Validated meeting records, extracted items, and answers."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DeadlineKind = Literal["explicit", "relative", "event", "time", "unresolved", "none"]
EvidenceType = Literal["explicit", "inferred"]
ItemKind = Literal["decision", "commitment", "task", "question", "status"]
ItemStatus = Literal[
    "open",
    "done",
    "dropped",
    "superseded",
    "resolved",
    "unresolved",
    "unconfirmed",
]
StatusEffect = Literal["none", "done", "dropped", "progress"]
Origin = Literal["transcript", "sidecar", "whisper"]
ProcessingStatus = Literal["ready", "needs_transcription", "failed"]
CommitmentState = Literal[
    "proposed",
    "committed",
    "in_progress",
    "completed",
    "deferred",
    "cancelled",
    "unconfirmed",
]
DecisionStatus = Literal[
    "confirmed",
    "proposed",
    "rejected",
    "deferred",
    "needs_confirmation",
]


class Evidence(BaseModel):
    meeting_id: str
    meeting_name: str
    held_on: str | None = None
    speaker: str | None = None
    start: str | None = None
    end: str | None = None
    start_seconds: float | None = None
    end_seconds: float | None = None
    quote: str = Field(min_length=1)
    source_path: str
    line_start: int | None = None


class Utterance(BaseModel):
    utterance_id: str
    index: int
    speaker: str | None = None
    source_speaker: str | None = None
    start: str | None = None
    end: str | None = None
    start_seconds: float | None = None
    end_seconds: float | None = None
    text: str = Field(min_length=1)
    line_start: int | None = None
    confidence: float | None = None


class Meeting(BaseModel):
    meeting_id: str
    name: str
    held_on: str | None = None
    held_at: str | None = None
    participants: list[str] = Field(default_factory=list)
    source_path: str
    transcript_path: str
    recording_filename: str | None = None
    origin: Origin
    language: str | None = None
    processing_status: ProcessingStatus = "ready"
    speaker_map: dict[str, str] = Field(default_factory=dict)
    speaker_map_confidence: dict[str, float] = Field(default_factory=dict)
    utterances: list[Utterance]


class MemoryItem(BaseModel):
    item_id: str
    meeting_id: str
    utterance_id: str
    utterance_index: int
    kind: ItemKind
    text: str = Field(min_length=1)
    owner: str | None = None
    deadline_wording: str | None = None
    deadline_iso: str | None = None
    deadline_kind: DeadlineKind = "none"
    prior_deadline_wording: str | None = None
    prior_deadline_iso: str | None = None
    prior_owner: str | None = None
    evidence_type: EvidenceType
    status: ItemStatus
    effect: StatusEffect = "none"
    commitment_state: CommitmentState | None = None
    decision_status: DecisionStatus | None = None
    priority: str | None = None
    depends_on: str | None = None
    supersedes: str | None = None
    superseded_by: str | None = None
    topic_tokens: list[str] = Field(default_factory=list)
    evidence: Evidence
    status_evidence: Evidence | None = None


class Corpus(BaseModel):
    version: int = 1
    meetings: list[Meeting] = Field(default_factory=list)
    items: list[MemoryItem] = Field(default_factory=list)


class RelatedCommitment(BaseModel):
    owner: str | None = None
    action: str
    deadline: str | None = None


class Answer(BaseModel):
    question: str
    abstained: bool
    reason: str | None = None
    text: str
    evidence: list[Evidence] = Field(default_factory=list)
    items: list[MemoryItem] = Field(default_factory=list)
    related_commitments: list[RelatedCommitment] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)


class MeetingSummary(BaseModel):
    meeting_id: str
    name: str
    held_on: str | None = None
    participants: list[str] = Field(default_factory=list)
    decisions: list[MemoryItem] = Field(default_factory=list)
    commitments: list[MemoryItem] = Field(default_factory=list)
    tasks: list[MemoryItem] = Field(default_factory=list)
    questions: list[MemoryItem] = Field(default_factory=list)
    markdown: str


class IngestReport(BaseModel):
    meetings_added: int
    meetings_total: int
    files_skipped: list[str] = Field(default_factory=list)
    files_needs_transcription: list[str] = Field(default_factory=list)
    files_failed: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    index_dir: str


class QuestionScore(BaseModel):
    id: str
    question: str
    passed: bool
    failures: list[str] = Field(default_factory=list)


class EvaluationReport(BaseModel):
    passed: int
    total: int
    scores: list[QuestionScore] = Field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return self.total > 0 and self.passed == self.total
