"""Connect commitments, completions, and questions across meetings.

Links are recomputed from the utterances every time a meeting is ingested.
A later sentence marks an earlier commitment done, dropped, or superseded.
A question stays unresolved when a later sentence says it is still open.
"""

from __future__ import annotations

import re

from meeting_memory.schemas import Meeting, MemoryItem
from meeting_memory.textutil import related

_UNRESOLVED_LANGUAGE = re.compile(
    r"\b(?:unresolved|open question|yet to be decided|tbd|to be decided)\b",
    re.IGNORECASE,
)


def link_items(meetings: list[Meeting], items: list[MemoryItem]) -> list[MemoryItem]:
    order = _meeting_order(meetings)
    ordered = sorted(items, key=lambda item: _key(item, order))
    _apply_status(ordered, order)
    _apply_revisions(ordered, order)
    _resolve_questions(ordered, order)
    _sync_states(ordered)
    return ordered


def meeting_sort_key(meeting: Meeting) -> tuple[str, str, str]:
    return (meeting.held_on or "9999-99-99", meeting.name.casefold(), meeting.source_path)


def _meeting_order(meetings: list[Meeting]) -> dict[str, int]:
    ordered = sorted(meetings, key=meeting_sort_key)
    return {meeting.meeting_id: index for index, meeting in enumerate(ordered)}


def _key(item: MemoryItem, order: dict[str, int]) -> tuple[int, int, str]:
    return (order.get(item.meeting_id, 10**6), item.utterance_index, item.item_id)


def _before(left: MemoryItem, right: MemoryItem, order: dict[str, int]) -> bool:
    return _key(left, order) < _key(right, order)


def _token_set(item: MemoryItem) -> set[str]:
    return set(item.topic_tokens)


def _best_prior(
    item: MemoryItem,
    candidates: list[MemoryItem],
    order: dict[str, int],
    kinds: set[str],
) -> MemoryItem | None:
    best: MemoryItem | None = None
    best_key: tuple[int, int, int, str] | None = None
    item_tokens = _token_set(item)
    for candidate in candidates:
        if candidate.item_id == item.item_id or candidate.kind not in kinds:
            continue
        if not _before(candidate, item, order):
            continue
        candidate_tokens = _token_set(candidate)
        if not related(item_tokens, candidate_tokens):
            continue
        score = len(item_tokens & candidate_tokens)
        key = (score, *_key(candidate, order))
        if best_key is None or key > best_key:
            best = candidate
            best_key = key
    return best


def _apply_status(items: list[MemoryItem], order: dict[str, int]) -> None:
    for item in items:
        if item.kind != "status" or item.effect not in {"done", "dropped", "progress"}:
            continue
        target = _best_prior(item, items, order, {"commitment", "task"})
        if target is None or target.status in {"superseded", "dropped"}:
            continue
        if item.effect == "progress":
            if target.status == "open":
                target.commitment_state = "in_progress"
            continue
        target.status = "done" if item.effect == "done" else "dropped"
        target.status_evidence = item.evidence


def _apply_revisions(items: list[MemoryItem], order: dict[str, int]) -> None:
    for item in items:
        if item.kind not in {"commitment", "task"} or item.status in {"done", "dropped"}:
            continue
        prior = _best_prior(item, items, order, {"commitment", "task"})
        if prior is None or prior.status in {"done", "dropped", "superseded"}:
            continue
        deadline_changed = bool(
            item.deadline_iso and prior.deadline_iso and item.deadline_iso != prior.deadline_iso
        )
        owner_changed = bool(item.owner and prior.owner and item.owner != prior.owner)
        said_change = bool(item.prior_deadline_iso or item.prior_deadline_wording)
        if not (deadline_changed or owner_changed or said_change):
            continue
        prior.status = "superseded"
        prior.superseded_by = item.item_id
        item.supersedes = prior.item_id
        if not item.prior_deadline_iso:
            item.prior_deadline_iso = prior.deadline_iso
            item.prior_deadline_wording = prior.deadline_wording
        if owner_changed and not item.prior_owner:
            item.prior_owner = prior.owner
        if not item.owner and prior.owner:
            item.owner = prior.owner


def _resolve_questions(items: list[MemoryItem], order: dict[str, int]) -> None:
    ordered = sorted(items, key=lambda item: _key(item, order))
    for index, item in enumerate(ordered):
        if item.kind != "question" or item.status != "unresolved":
            continue
        item_tokens = _token_set(item)
        for later in ordered[index + 1 :]:
            if _deadline_answer(item, later):
                item.status = "resolved"
                item.status_evidence = later.evidence
                break
            if not related(item_tokens, _token_set(later)):
                continue
            if later.kind == "question" or _UNRESOLVED_LANGUAGE.search(later.text):
                item.status = "superseded"
                item.superseded_by = later.item_id
                break
            if later.kind == "status" and later.effect in {"none", "progress"}:
                continue
            if later.status == "unconfirmed":
                continue
            item.status = "resolved"
            item.status_evidence = later.evidence
            break


def _deadline_key(item: MemoryItem) -> str:
    return re.sub(r"\s+", " ", (item.deadline_wording or "")).strip().casefold()


def _deadline_answer(question: MemoryItem, later: MemoryItem) -> bool:
    """A nearby explicit commitment with the same deadline answers the question.

    Token overlap is not enough for "by December 5?" followed by "by December 5."
    A shared short token such as "api" must not resolve a different question.
    """

    wording = _deadline_key(question)
    if not wording or wording != _deadline_key(later):
        return False
    if later.meeting_id != question.meeting_id:
        return False
    gap = later.utterance_index - question.utterance_index
    if not 0 < gap <= 3:
        return False
    if later.kind not in {"commitment", "task"} or later.evidence_type != "explicit":
        return False
    if later.status == "unconfirmed":
        return False
    return True


def _sync_states(items: list[MemoryItem]) -> None:
    for item in items:
        if item.kind not in {"commitment", "task"}:
            continue
        if item.status == "done":
            item.commitment_state = "completed"
        elif item.status == "dropped":
            item.commitment_state = "cancelled"
        elif item.status == "unconfirmed":
            item.commitment_state = "unconfirmed"
        elif item.commitment_state == "in_progress" and item.status == "open":
            continue
        elif item.evidence_type == "inferred":
            item.commitment_state = "proposed"
        elif item.status == "open":
            item.commitment_state = "committed"


def is_revision(item: MemoryItem) -> bool:
    if item.kind not in {"commitment", "task"}:
        return False
    if item.prior_deadline_iso and item.deadline_iso and item.prior_deadline_iso != item.deadline_iso:
        return True
    if item.prior_owner and item.owner and item.prior_owner != item.owner:
        return True
    return False
