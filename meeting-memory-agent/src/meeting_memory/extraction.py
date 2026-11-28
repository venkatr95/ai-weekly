"""Rule extraction of decisions, commitments, tasks, questions, and status.

A sentence is an explicit agreement only when the wording says so: decided,
agreed, will, or own. "Should" and "needs to" stay inferred. Instructions
inside a transcript are ordinary sentences and do not change these rules.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date

from meeting_memory.dates import ParsedDeadline, parse_deadlines
from meeting_memory.schemas import Evidence, Meeting, MemoryItem
from meeting_memory.textutil import tokens
from meeting_memory.timestamps import to_seconds

_SMALLTALK = re.compile(
    r"(?:thanks|thank you|hi|hello|hey|ok|okay|sure|sounds good|goodbye|bye)[.!]?",
    re.IGNORECASE,
)
_UNRESOLVED = re.compile(
    r"\b(?:open question|still unresolved|remains unresolved|yet to be decided|"
    r"to be decided|\btbd\b|unresolved|still need to decide|need to decide whether|"
    r"have not decided|haven't decided|remains to be decided)\b",
    re.IGNORECASE,
)
_WHETHER = re.compile(r"\bwhether\b.+\bor\b", re.IGNORECASE)
_REJECTED = re.compile(
    r"\b(?:rejected|voted against|decided not to|decision is no)\b",
    re.IGNORECASE,
)
_DEFERRED = re.compile(
    r"\b(?:defer(?:red)?|postpone(?:d)?|decide later|revisit later|put off)\b",
    re.IGNORECASE,
)
_NEEDS_CONFIRM = re.compile(
    r"\b(?:needs confirmation|need to confirm|pending confirmation|subject to confirmation)\b",
    re.IGNORECASE,
)
_PROPOSED = re.compile(
    r"\b(?:i propose|we propose|the proposal is|proposed that)\b",
    re.IGNORECASE,
)
_DROP = re.compile(
    r"\b(?:cancelled|canceled|dropped|will not|won't|no longer)\b",
    re.IGNORECASE,
)
_FUTURE = re.compile(
    r"\b(?:i will|i'll|i commit to|i am going to|i'm going to|we will|we'll)\b",
    re.IGNORECASE,
)
_OFFER = re.compile(
    r"\b(?:i can|i could|i'm able to|i am able to)\b",
    re.IGNORECASE,
)
_PROGRESS = re.compile(
    r"\b(?:in progress|working on|i am working|i'm working|i have started|i started)\b",
    re.IGNORECASE,
)
_DONE = re.compile(r"\b(?:done|completed|complete|finished|shipped)\b", re.IGNORECASE)
_DECISION = re.compile(
    r"\b(?:we (?:have )?(?:decided|agreed)(?:\s+to|\s+that|\s+on)?|"
    r"(?:it is|it's) (?:decided|agreed)|the decision is|we (?:will|'ll) go with|"
    r"decision\s*:)\b",
    re.IGNORECASE,
)
_OWN = re.compile(r"\b(?:I|([A-Z][a-z]+))\s+(?:own|owns|will own)\b")
_NAMED_WILL = re.compile(r"\b([A-Z][a-z]+)\s+will\b")
_PLEASE = re.compile(r"\b(?:please|can you|could you|action item)\b", re.IGNORECASE)
_INFER = re.compile(r"\b(?:should|needs to|need to|ought to)\b", re.IGNORECASE)
_NAME_PLEASE = re.compile(r"\b([A-Z][a-z]+),\s*please\b")
_NAME_SHOULD = re.compile(r"\b([A-Z][a-z]+)\s+should\b")
_NAME_STOP = {
    "what", "when", "where", "who", "why", "how", "this", "that", "there",
    "they", "we", "it", "the", "someone", "somebody", "please", "meeting",
    "date", "participants", "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday", "january", "february", "march", "april",
    "june", "july", "august", "september", "october", "november", "december",
}


@dataclass
class _Draft:
    kind: str
    text: str
    owner: str | None
    evidence_type: str
    status: str
    effect: str
    deadline: ParsedDeadline | None
    utterance_index: int
    utterance_id: str
    speaker: str | None
    start: str | None
    end: str | None
    line_start: int | None
    decision_status: str | None = None
    commitment_state: str | None = None
    priority: str | None = None
    depends_on: str | None = None


def extract_items(meetings: list[Meeting]) -> list[MemoryItem]:
    items: list[MemoryItem] = []
    for meeting in meetings:
        meeting_date = date.fromisoformat(meeting.held_on) if meeting.held_on else None
        for utterance in meeting.utterances:
            for sentence in split_sentences(utterance.text):
                draft = classify_sentence(
                    sentence,
                    utterance.speaker,
                    meeting_date,
                    utterance_index=utterance.index,
                    utterance_id=utterance.utterance_id,
                    start=utterance.start,
                    end=utterance.end,
                    line_start=utterance.line_start,
                )
                if draft is None:
                    continue
                items.append(_to_item(meeting, draft))
    return items


def split_sentences(text: str) -> list[str]:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return []
    parts = re.split(r"(?<=[.?!])\s+(?=[A-Z0-9\"'])", compact)
    return [part.strip() for part in parts if part.strip()]


def classify_sentence(
    sentence: str,
    speaker: str | None,
    meeting_date: date | None,
    *,
    utterance_index: int = 0,
    utterance_id: str = "utt",
    start: str | None = None,
    end: str | None = None,
    line_start: int | None = None,
) -> _Draft | None:
    cleaned = sentence.strip()
    if not cleaned or _SMALLTALK.fullmatch(cleaned):
        return None
    deadline = parse_deadlines(cleaned, meeting_date)
    priority = _priority(cleaned)
    depends_on = _depends_on(cleaned)
    common = (
        speaker, utterance_index, utterance_id, start, end, line_start, priority, depends_on,
    )
    if _is_question(cleaned):
        return _draft(
            "question", cleaned, None, "explicit", "unresolved", "none", deadline, *common,
        )
    if _REJECTED.search(cleaned):
        return _draft(
            "decision", cleaned, None, "explicit", "dropped", "none", deadline, *common,
            decision_status="rejected",
        )
    if _DEFERRED.search(cleaned) and not _FUTURE.search(cleaned):
        return _draft(
            "decision", cleaned, None, "explicit", "open", "none", deadline, *common,
            decision_status="deferred",
        )
    if _NEEDS_CONFIRM.search(cleaned):
        return _draft(
            "decision", cleaned, None, "explicit", "open", "none", deadline, *common,
            decision_status="needs_confirmation",
        )
    if _DROP.search(cleaned):
        return _draft(
            "status", cleaned, _owner(cleaned, speaker), "explicit", "open", "dropped",
            deadline, *common,
        )
    if _FUTURE.search(cleaned) or _OWN.search(cleaned) or _named_will(cleaned):
        return _draft(
            "commitment", cleaned, _owner(cleaned, speaker), "explicit", "open", "none",
            deadline, *common, commitment_state="committed",
        )
    if _OFFER.search(cleaned):
        return _draft(
            "commitment", cleaned, _owner(cleaned, speaker), "explicit", "unconfirmed", "none",
            deadline, *common, commitment_state="unconfirmed",
        )
    if _PROGRESS.search(cleaned):
        return _draft(
            "status", cleaned, _owner(cleaned, speaker), "explicit", "open", "progress",
            deadline, *common,
        )
    if _DONE.search(cleaned):
        return _draft(
            "status", cleaned, _owner(cleaned, speaker), "explicit", "open", "done",
            deadline, *common,
        )
    if _DECISION.search(cleaned):
        return _draft(
            "decision", cleaned, None, "explicit", "open", "none", deadline, *common,
            decision_status="confirmed",
        )
    if _PROPOSED.search(cleaned):
        return _draft(
            "decision", cleaned, None, "explicit", "open", "none", deadline, *common,
            decision_status="proposed",
        )
    if _PLEASE.search(cleaned):
        return _draft(
            "task", cleaned, _owner(cleaned, speaker), "explicit", "open", "none",
            deadline, *common, commitment_state="committed",
        )
    if _INFER.search(cleaned):
        return _draft(
            "task", cleaned, _inferred_owner(cleaned), "inferred", "open", "none",
            deadline, *common, commitment_state="proposed",
        )
    return None


def _is_question(sentence: str) -> bool:
    if sentence.endswith("?"):
        return True
    if _DECISION.search(sentence) or _FUTURE.search(sentence):
        return False
    if _UNRESOLVED.search(sentence):
        return True
    if _WHETHER.search(sentence) and not _PROPOSED.search(sentence):
        return True
    return False


def _named_will(sentence: str) -> bool:
    match = _NAMED_WILL.search(sentence)
    return bool(match and match.group(1).lower() not in _NAME_STOP)


def _priority(sentence: str) -> str | None:
    if re.search(r"\b(?:urgent|high priority|asap)\b", sentence, re.IGNORECASE):
        return "high"
    if re.search(r"\blow priority\b", sentence, re.IGNORECASE):
        return "low"
    return None


def _depends_on(sentence: str) -> str | None:
    match = re.search(
        r"\bdepends on\s+(?:the\s+)?([A-Za-z][A-Za-z0-9 ]{2,40})",
        sentence,
        re.IGNORECASE,
    )
    if not match:
        return None
    return match.group(1).strip().rstrip(".")


def _owner(sentence: str, speaker: str | None) -> str | None:
    if re.search(
        r"\b(?:i will|i'll|i commit|i'm going|i am going|i own|i will own|i can|i could)\b",
        sentence,
        re.IGNORECASE,
    ):
        return speaker
    please = _NAME_PLEASE.search(sentence)
    if please and please.group(1).lower() not in _NAME_STOP:
        return please.group(1)
    named = _NAMED_WILL.search(sentence)
    if named and named.group(1).lower() not in _NAME_STOP:
        return named.group(1)
    own = re.search(r"\b([A-Z][a-z]+)\s+owns\b", sentence)
    if own and own.group(1).lower() not in _NAME_STOP:
        return own.group(1)
    return None


def _inferred_owner(sentence: str) -> str | None:
    match = _NAME_SHOULD.search(sentence)
    if match and match.group(1).lower() not in _NAME_STOP:
        return match.group(1)
    return None


def _draft(
    kind: str,
    text: str,
    owner: str | None,
    evidence_type: str,
    status: str,
    effect: str,
    deadline: ParsedDeadline | None,
    speaker: str | None,
    utterance_index: int,
    utterance_id: str,
    start: str | None,
    end: str | None,
    line_start: int | None,
    priority: str | None,
    depends_on: str | None,
    decision_status: str | None = None,
    commitment_state: str | None = None,
) -> _Draft:
    return _Draft(
        kind=kind,
        text=text,
        owner=owner,
        evidence_type=evidence_type,
        status=status,
        effect=effect,
        deadline=deadline,
        utterance_index=utterance_index,
        utterance_id=utterance_id,
        speaker=speaker,
        start=start,
        end=end,
        line_start=line_start,
        decision_status=decision_status,
        commitment_state=commitment_state,
        priority=priority,
        depends_on=depends_on,
    )


def _to_item(meeting: Meeting, draft: _Draft) -> MemoryItem:
    deadline = draft.deadline
    item_id = _stable_id(
        "itm",
        meeting.meeting_id,
        draft.utterance_id,
        draft.kind,
        draft.text,
    )
    return MemoryItem(
        item_id=item_id,
        meeting_id=meeting.meeting_id,
        utterance_id=draft.utterance_id,
        utterance_index=draft.utterance_index,
        kind=draft.kind,  # type: ignore[arg-type]
        text=draft.text,
        owner=draft.owner,
        deadline_wording=deadline.wording if deadline else None,
        deadline_iso=deadline.iso if deadline else None,
        deadline_kind=(deadline.kind if deadline and deadline.wording else "none"),  # type: ignore[arg-type]
        prior_deadline_wording=deadline.prior_wording if deadline else None,
        prior_deadline_iso=deadline.prior_iso if deadline else None,
        evidence_type=draft.evidence_type,  # type: ignore[arg-type]
        status=draft.status,  # type: ignore[arg-type]
        effect=draft.effect,  # type: ignore[arg-type]
        commitment_state=draft.commitment_state,  # type: ignore[arg-type]
        decision_status=draft.decision_status,  # type: ignore[arg-type]
        priority=draft.priority,
        depends_on=draft.depends_on,
        topic_tokens=tokens(draft.text),
        evidence=Evidence(
            meeting_id=meeting.meeting_id,
            meeting_name=meeting.name,
            held_on=meeting.held_on,
            speaker=draft.speaker,
            start=draft.start,
            end=draft.end,
            start_seconds=to_seconds(draft.start),
            end_seconds=to_seconds(draft.end),
            quote=draft.text,
            source_path=meeting.source_path,
            line_start=draft.line_start,
        ),
    )


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"
