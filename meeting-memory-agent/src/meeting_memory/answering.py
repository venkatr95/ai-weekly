"""Answer meeting questions from extracted records.

Every positive claim cites a transcript passage. If nothing in the index
matches the question, the answer abstains. A question with no remaining
matches can still be a supported negative, such as "no commitment was revised."
"""

from __future__ import annotations

import re

from meeting_memory.linking import is_revision, meeting_sort_key
from meeting_memory.retrieval import hybrid_search
from meeting_memory.schemas import Answer, Evidence, Meeting, MemoryItem, RelatedCommitment
from meeting_memory.textutil import overlap_count, related, required_tokens, tokens

_UNRESOLVED = re.compile(
    r"\b(?:unresolved|open questions|remain unresolved|still open|remain open)\b",
    re.IGNORECASE,
)
_CHANGES = re.compile(r"\b(?:changed|changes|change|revised|revision|updated)\b", re.IGNORECASE)
_PREVIOUS = re.compile(r"\b(?:previous|last|earlier|prior)\s+meeting\b", re.IGNORECASE)
_DECISIONS = re.compile(r"\b(?:decision|decisions|decide|decided)\b", re.IGNORECASE)
_WHEN = re.compile(r"\b(?:when|deadline|ready|due|expected)\b", re.IGNORECASE)
_WHO = re.compile(r"\bwho\b", re.IGNORECASE)
_OWNER_QUERY = re.compile(
    r"\b(?:belong to|assigned to|owned by|tasks for|commitments for)\b",
    re.IGNORECASE,
)
_SUMMARY = re.compile(r"\bsummar", re.IGNORECASE)
_LEADING = re.compile(
    r"^(?:yes,\s*)?(?:i will|i'll|i can|i could|we will|we'll|i commit to)\s+",
    re.IGNORECASE,
)


def answer_question(meetings: list[Meeting], items: list[MemoryItem], question: str) -> Answer:
    if not meetings:
        return _abstain(question, "no_meetings", "No meetings are indexed.")
    intent = _intent(question)
    required = required_tokens(question)
    if intent == "unresolved":
        return _unresolved(question, items, required)
    if intent == "changes":
        return _changes(question, items, required)
    if intent == "previous":
        return _previous(question, meetings, items, required)
    if intent == "decisions":
        return _decisions(question, items, required)
    if intent == "when":
        return _when(question, items, required)
    if intent == "who":
        return _who(question, items, required)
    if intent == "summary":
        return _summary(question, meetings, items)
    return _search(question, items, required)


def compare_topic(meetings: list[Meeting], items: list[MemoryItem], topic: str) -> Answer:
    if not meetings:
        return _abstain(topic, "no_meetings", "No meetings are indexed.")
    required = set(tokens(topic))
    if not required:
        return _abstain(topic, "no_matching_evidence", "No indexed meeting records a statement about that subject.")
    matched = [
        item
        for item in items
        if item.kind in {"decision", "commitment", "task", "question"}
        and related(required, set(item.topic_tokens))
    ]
    if not matched:
        return _abstain(topic, "no_matching_evidence", "No indexed meeting records a statement about that subject.")
    matched = _chronological(matched, meetings)
    sentences = [f"Records about {topic}:"]
    evidence: list[Evidence] = []
    for item in matched:
        evidence.extend(_evidence_for(item, _by_id(items), include_prior=is_revision(item)))
        sentences.append(
            f"{item.evidence.meeting_name} ({item.evidence.held_on or 'undated'}) "
            f"{item.kind}, {item.evidence_type}, {item.status}: {item.text}"
        )
    return Answer(
        question=topic,
        abstained=False,
        text=" ".join(sentences),
        evidence=_unique(evidence),
        items=matched,
    )


def _intent(question: str) -> str:
    if _UNRESOLVED.search(question):
        return "unresolved"
    if _CHANGES.search(question):
        return "changes"
    if _PREVIOUS.search(question):
        return "previous"
    if _DECISIONS.search(question):
        return "decisions"
    if _WHEN.search(question):
        return "when"
    if _WHO.search(question) or _OWNER_QUERY.search(question):
        return "who"
    if _SUMMARY.search(question):
        return "summary"
    return "search"


def _who(question: str, items: list[MemoryItem], required: list[str]) -> Answer:
    matched = _match(items, required, {"commitment", "task"}, {"open", "done", "dropped"})
    if not matched and required:
        matched = _match(items, required, {"commitment", "task"}, {"superseded"})
    if not matched:
        return _abstain(question, "no_matching_evidence", "No indexed meeting records a statement about that subject.")
    chosen = _prefer(matched, required)
    return _from_items(question, chosen, items, include_prior=True)


def _when(question: str, items: list[MemoryItem], required: list[str]) -> Answer:
    matched = _match(items, required, {"commitment", "task"}, {"open", "done", "dropped"})
    matched = [item for item in matched if item.deadline_iso or item.deadline_wording]
    if not matched:
        return _abstain(question, "no_matching_evidence", "No indexed meeting records a statement about that subject.")
    open_items = [item for item in matched if item.status == "open"]
    chosen = _prefer(open_items or matched, required)
    current = [item for item in chosen if item.status == "open"] or chosen
    deadlines = {item.deadline_iso for item in current if item.deadline_iso}
    if len(deadlines) <= 1:
        current = current[:1]
    return _from_items(question, current, items, include_prior=True)


def _decisions(question: str, items: list[MemoryItem], required: list[str]) -> Answer:
    matched = _match(items, required, {"decision"}, {"open", "superseded", "dropped"})
    if not matched:
        return _unresolved_decision(question, items, required)
    sentences = [_decision_sentence(item) for item in matched]
    evidence = [item.evidence for item in matched]
    _, unresolved = _companions(matched, items)
    return Answer(
        question=question,
        abstained=False,
        text=" ".join(sentences),
        evidence=_unique(evidence),
        items=matched,
        unresolved_questions=unresolved,
    )


def _unresolved_decision(question: str, items: list[MemoryItem], required: list[str]) -> Answer:
    if not required:
        return _abstain(question, "no_matching_evidence", "No indexed meeting records a statement about that subject.")
    questions = _match(items, required, {"question"}, {"unresolved"})
    if not questions:
        return _abstain(question, "no_matching_evidence", "No indexed meeting records a statement about that subject.")
    sentences = ["No confirmed decision is recorded."]
    evidence: list[Evidence] = []
    for item in questions:
        sentences.append(f"Unresolved question: {item.text}")
        evidence.append(item.evidence)
    return Answer(
        question=question,
        abstained=False,
        text=" ".join(sentences),
        evidence=_unique(evidence),
        items=questions,
        unresolved_questions=[item.text for item in questions],
    )


def _decision_sentence(item: MemoryItem) -> str:
    speaker = item.evidence.speaker or "An unnamed speaker"
    held = item.evidence.held_on or "undated"
    where = f"in {item.evidence.meeting_name} ({held}), stated by {speaker}: {item.text}"
    if item.decision_status == "proposed":
        return f"Proposed decision, not confirmed, {where}"
    if item.decision_status == "deferred":
        return f"Deferred decision {where}"
    if item.decision_status == "rejected":
        return f"Rejected proposal {where}"
    if item.decision_status == "needs_confirmation":
        return f"Decision needing confirmation {where}"
    return f"Explicit decision {where}"


def _unresolved(question: str, items: list[MemoryItem], required: list[str]) -> Answer:
    matched = [item for item in items if item.kind == "question" and item.status == "unresolved"]
    if required:
        required_set = set(required)
        matched = [item for item in matched if related(required_set, set(item.topic_tokens))]
    if not matched:
        return Answer(
            question=question,
            abstained=False,
            text="No unresolved questions are recorded.",
            evidence=[],
            items=[],
        )
    sentences = []
    evidence: list[Evidence] = []
    for item in matched:
        speaker = item.evidence.speaker or "An unnamed speaker"
        sentences.append(f"Unresolved question from {item.evidence.meeting_name}: {item.text} ({speaker}).")
        evidence.append(item.evidence)
    return Answer(
        question=question,
        abstained=False,
        text=" ".join(sentences),
        evidence=_unique(evidence),
        items=matched,
    )


def _changes(question: str, items: list[MemoryItem], required: list[str]) -> Answer:
    matched = [item for item in items if is_revision(item)]
    if required:
        required_set = set(required)
        matched = [item for item in matched if related(required_set, set(item.topic_tokens))]
    if not matched:
        return Answer(
            question=question,
            abstained=False,
            text="No previous commitment was revised in the indexed meetings.",
            evidence=[],
            items=[],
        )
    by_id = _by_id(items)
    sentences = []
    evidence: list[Evidence] = []
    for item in matched:
        owner = item.owner or "An unnamed speaker"
        prior = item.prior_deadline_iso or item.prior_deadline_wording or "an earlier deadline"
        current = item.deadline_iso or item.deadline_wording or "an unstated deadline"
        sentences.append(
            f"{owner} revised a commitment from {prior} to {current}. "
            f"This is an explicit commitment. Current wording: {item.text}"
        )
        evidence.extend(_evidence_for(item, by_id, include_prior=True))
    return Answer(
        question=question,
        abstained=False,
        text=" ".join(sentences),
        evidence=_unique(evidence),
        items=matched,
    )


def _previous(
    question: str,
    meetings: list[Meeting],
    items: list[MemoryItem],
    required: list[str],
) -> Answer:
    ordered = sorted(meetings, key=meeting_sort_key)
    if len(ordered) < 2:
        only = ordered[0]
        held = f" ({only.held_on})" if only.held_on else ""
        return Answer(
            question=question,
            abstained=False,
            text=f"Only one meeting is indexed ({only.name}{held}), so there is no previous meeting.",
            evidence=[],
            items=[],
        )
    previous = ordered[-2]
    matched = [
        item
        for item in items
        if item.meeting_id == previous.meeting_id
        and item.kind in {"decision", "commitment", "task"}
        and item.evidence_type == "explicit"
        and item.status != "unconfirmed"
        and item.decision_status not in {"proposed", "deferred", "needs_confirmation"}
    ]
    if required:
        required_set = set(required)
        matched = [item for item in matched if related(required_set, set(item.topic_tokens))]
    if not matched:
        return _abstain(question, "no_matching_evidence", "No indexed meeting records a statement about that subject.")
    matched = sorted(matched, key=lambda item: (item.utterance_index, item.item_id))
    held = previous.held_on or "undated"
    sentences = [f"The previous meeting is {previous.name} ({held}). Explicit agreements:"]
    evidence: list[Evidence] = []
    for item in matched:
        owner = f"{item.owner}: " if item.owner else ""
        sentences.append(f"{owner}{item.text}")
        evidence.append(item.evidence)
    return Answer(
        question=question,
        abstained=False,
        text=" ".join(sentences),
        evidence=_unique(evidence),
        items=matched,
    )


def _summary(question: str, meetings: list[Meeting], items: list[MemoryItem]) -> Answer:
    ordered = sorted(meetings, key=meeting_sort_key)
    sentences = [f"{len(ordered)} meetings are indexed."]
    evidence: list[Evidence] = []
    cited: list[MemoryItem] = []
    for meeting in ordered:
        decisions = [
            item for item in items if item.meeting_id == meeting.meeting_id and item.kind == "decision"
        ]
        commitments = [
            item
            for item in items
            if item.meeting_id == meeting.meeting_id and item.kind == "commitment" and item.status != "superseded"
        ]
        sentences.append(f"{meeting.name}: {len(decisions)} decisions, {len(commitments)} current commitments.")
        for item in decisions + commitments:
            evidence.append(item.evidence)
            cited.append(item)
    return Answer(
        question=question,
        abstained=False,
        text=" ".join(sentences),
        evidence=_unique(evidence),
        items=cited,
    )


def _search(question: str, items: list[MemoryItem], required: list[str]) -> Answer:
    matched = _match(
        items,
        required,
        {"decision", "commitment", "task", "question"},
        {"open", "done", "dropped", "unresolved", "resolved", "superseded"},
    )
    if not matched:
        return _abstain(question, "no_matching_evidence", "No indexed meeting records a statement about that subject.")
    chosen = hybrid_search(matched, question, limit=3) or _prefer(matched, required)[:3]
    return _from_items(question, chosen, items, include_prior=False)


def _from_items(
    question: str,
    chosen: list[MemoryItem],
    items: list[MemoryItem],
    *,
    include_prior: bool,
) -> Answer:
    by_id = _by_id(items)
    sentences = [_describe(item) for item in chosen]
    evidence: list[Evidence] = []
    for item in chosen:
        evidence.extend(_evidence_for(item, by_id, include_prior=include_prior and is_revision(item)))
    related, unresolved = _companions(chosen, items)
    conflicts = _conflicts(chosen)
    return Answer(
        question=question,
        abstained=False,
        text=" ".join(sentences),
        evidence=_unique(evidence),
        items=chosen,
        related_commitments=related,
        unresolved_questions=unresolved,
        conflicts=conflicts,
    )


def action_text(text: str) -> str:
    cleaned = text.strip().rstrip(".")
    stripped = _LEADING.sub("", cleaned).strip()
    if not stripped or stripped == cleaned:
        return cleaned
    return stripped[:1].upper() + stripped[1:]


def _describe(item: MemoryItem) -> str:
    if item.evidence_type == "inferred" or item.status == "unconfirmed":
        speaker = item.evidence.speaker or "An unnamed speaker"
        if item.status == "unconfirmed":
            owner = item.owner or speaker
            sentence = (
                f"{owner} offered to take this on. That is not a confirmed agreement. {item.text}"
            )
        elif item.owner:
            sentence = (
                f"This is inferred, not an agreement. {item.owner} is only an inferred owner. {item.text}"
            )
        else:
            sentence = (
                f"This is inferred, not an agreement. {speaker} said: {item.text} No owner is named."
            )
    else:
        sentence = _agreement_sentence(item)
        if item.evidence_type == "explicit":
            sentence += " This is an explicit commitment."
    if item.prior_deadline_iso and item.deadline_iso and item.prior_deadline_iso != item.deadline_iso:
        sentence += (
            f" The current deadline is {item.deadline_iso}, revised from {item.prior_deadline_iso}."
        )
    elif item.deadline_iso:
        sentence += f" The deadline is {item.deadline_iso}."
    elif item.deadline_wording:
        sentence += f" The deadline wording is {item.deadline_wording}."
    if item.status == "done":
        sentence += " The commitment is done."
    elif item.status == "dropped":
        sentence += " The commitment was dropped."
    return sentence


def _agreement_sentence(item: MemoryItem) -> str:
    owner = item.owner or "An unnamed speaker"
    if _LEADING.match(item.text.strip()):
        phrase = action_text(item.text)
        phrase = phrase[:1].lower() + phrase[1:] if phrase else item.text
        return f"{owner} agreed to {phrase}."
    return f"{owner} — explicit commitment: {item.text}"


def _companions(
    chosen: list[MemoryItem],
    items: list[MemoryItem],
) -> tuple[list[RelatedCommitment], list[str]]:
    meeting_ids = {item.meeting_id for item in chosen}
    cited = {item.item_id for item in chosen}
    related: list[RelatedCommitment] = []
    unresolved: list[str] = []
    for item in items:
        if item.meeting_id not in meeting_ids:
            continue
        if item.kind == "question" and item.status == "unresolved":
            unresolved.append(item.text)
            continue
        if item.item_id in cited or item.kind not in {"commitment", "task"}:
            continue
        if item.status in {"superseded", "unconfirmed"} or item.evidence_type != "explicit":
            continue
        related.append(
            RelatedCommitment(
                owner=item.owner,
                action=action_text(item.text),
                deadline=item.deadline_iso,
            )
        )
    return related, unresolved


def _conflicts(chosen: list[MemoryItem]) -> list[str]:
    deadlines = sorted({item.deadline_iso for item in chosen if item.status == "open" and item.deadline_iso})
    if len(deadlines) < 2:
        return []
    return ["Open commitments name different deadlines: " + ", ".join(deadlines) + "."]


def _match(
    items: list[MemoryItem],
    required: list[str],
    kinds: set[str],
    statuses: set[str],
) -> list[MemoryItem]:
    pool = [item for item in items if item.kind in kinds and item.status in statuses]
    if not required:
        return pool
    required_set = set(required)
    found: list[MemoryItem] = []
    for item in pool:
        topic = set(item.topic_tokens)
        if related(required_set, topic):
            found.append(item)
            continue
        owner = (item.owner or "").casefold()
        if not owner or owner not in required_set:
            continue
        others = required_set - {owner}
        if not others or related(others, topic):
            found.append(item)
    return found


def _prefer(items: list[MemoryItem], required: list[str]) -> list[MemoryItem]:
    required_set = set(required)

    def sort_key(item: MemoryItem) -> tuple[int, int, int, str]:
        score = overlap_count(required_set, set(item.topic_tokens)) if required else 0
        explicit = 1 if item.evidence_type == "explicit" else 0
        return (score, explicit, item.utterance_index, item.item_id)

    return sorted(items, key=sort_key, reverse=True)


def _chronological(items: list[MemoryItem], meetings: list[Meeting]) -> list[MemoryItem]:
    order = {meeting.meeting_id: index for index, meeting in enumerate(sorted(meetings, key=meeting_sort_key))}
    return sorted(
        items,
        key=lambda item: (order.get(item.meeting_id, 10**6), item.utterance_index, item.item_id),
    )


def _evidence_for(item: MemoryItem, by_id: dict[str, MemoryItem], *, include_prior: bool) -> list[Evidence]:
    found = [item.evidence]
    if item.status_evidence is not None:
        found.append(item.status_evidence)
    if include_prior and item.supersedes and item.supersedes in by_id:
        found.append(by_id[item.supersedes].evidence)
    return found


def _by_id(items: list[MemoryItem]) -> dict[str, MemoryItem]:
    return {item.item_id: item for item in items}


def _unique(evidence: list[Evidence]) -> list[Evidence]:
    seen: set[tuple[str, str | None, str]] = set()
    unique: list[Evidence] = []
    for item in evidence:
        key = (item.meeting_id, item.start, item.quote)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _abstain(question: str, reason: str, text: str) -> Answer:
    return Answer(question=question, abstained=True, reason=reason, text=text, evidence=[], items=[])
