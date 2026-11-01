"""Extract tasks, owners, deadlines, questions, and commitments from messages."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from email_to_action.dates import day_before, resolve_deadline, split_deadline
from email_to_action.schemas import (
    Commitment,
    Confidence,
    DatePrecision,
    Deadline,
    DeadlineKind,
    EmailMessage,
    EvidenceType,
    Owner,
    PriorityLevel,
    Question,
    QuestionKind,
    Task,
    TaskStatus,
)
from email_to_action.textutil import clean_description, tokens

_BULLET = re.compile(r"^(?:[-*•]|\d+[.)])\s+(?P<body>.+)$")
_INTRO = re.compile(
    r"^(?:(?:could|can|would)\s+you(?:\s+please)?|please(?:\s+do the following)?|action items|to-?dos?)\s*:?\s*$",
    re.IGNORECASE,
)
_NAMED = re.compile(
    r"^(?P<name>[A-Z][A-Za-z]+(?:\s+[A-Za-z]+){0,3}),?\s+please\s+(?P<task>.+)$"
)
_NEED_YOU = re.compile(r"^(?:i|we)'?ll\s+need\s+you\s+to\s+(?P<task>.+)$", re.IGNORECASE)
_YOU = re.compile(r"^(?:(?:could|can|would)\s+you(?:\s+please)?|please)\s+(?P<task>.+)$", re.IGNORECASE)
_NEED = re.compile(
    r"^(?:we|i|the team)\s+(?:really\s+|still\s+)?(?:need to|must|have to)\s+(?P<task>.+)$",
    re.IGNORECASE,
)
_LETS = re.compile(r"^let'?s\s+(?P<task>.+)$", re.IGNORECASE)
_SHOULD = re.compile(r"^(?:we|i|someone)\s+should(?:\s+probably|\s+maybe)?\s+(?P<task>.+)$", re.IGNORECASE)
_COMMIT = re.compile(r"^(?:(?:i|we)\s+will|(?:i|we)'ll)\s+(?P<task>.+)$", re.IGNORECASE)
_IMPLIED = re.compile(
    r"^(?:the\s+)?(?P<thing>.+?)\s+(?:still\s+)?(?:needs to be|needs a|needs an|is missing)\s+(?P<rest>.+)$",
    re.IGNORECASE,
)
_IMPERATIVE = re.compile(
    r"^(?:please\s+)?(?:send|complete|review|schedule|confirm|approve|prepare|update|share|deliver|"
    r"finish|draft|write|book|arrange|call|email|forward|attach|provide|check|verify|finalize|finalise|"
    r"create|add|fix|upload|submit|reply|respond|coordinate|follow|ask|notify|revise|edit|design|build|"
    r"test|publish|make|get)\b",
    re.IGNORECASE,
)
_GREETING = re.compile(r"^(?:hi|hello|dear|hey)\s+.+$", re.IGNORECASE)
_STRONG = re.compile(
    r"\b(as soon as possible|time-sensitive|immediately|urgent|asap|critical|blocker)\b",
    re.IGNORECASE,
)
_WEAK = re.compile(r"\b(finalize|finalise|required|need to|needs to|must)\b", re.IGNORECASE)
_LOW = re.compile(
    r"\b(no rush|nice to have|low priority|when you can|when you have time|if you have time|whenever)\b",
    re.IGNORECASE,
)
_DONE = re.compile(
    r"\b(went out|has been sent|have been sent|i've sent|i sent|already sent|is done|are done|"
    r"is complete|marked complete|finished the|completed the|shipped the)\b",
    re.IGNORECASE,
)
_MISSING = re.compile(
    r"\b(?:still\s+)?need the\b.+\b(address|number|link|file|details|information)\b",
    re.IGNORECASE,
)
_TEAMS = {
    "engineering",
    "marketing",
    "sales",
    "support",
    "legal",
    "finance",
    "design",
    "product",
    "hr",
    "ops",
    "operations",
    "qa",
    "security",
}
_DATED = {DatePrecision.day, DatePrecision.time, DatePrecision.range}


@dataclass
class Extraction:
    tasks: list[Task] = field(default_factory=list)
    questions: list[Question] = field(default_factory=list)
    commitments: list[Commitment] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class _Draft:
    description: str
    owner_mode: str
    owner_name: str | None
    wording: str | None
    hint: str
    evidence_type: EvidenceType
    confidence: Confidence
    supporting_text: str
    message: EmailMessage
    preamble: str
    commitment: bool = False


@dataclass
class _QuestionDraft:
    text: str
    original_wording: str
    message: EmailMessage
    directed_to: str | None
    kind: QuestionKind


def extract(messages: list[EmailMessage], received_at: datetime | None = None) -> Extraction:
    drafts: list[_Draft] = []
    question_drafts: list[_QuestionDraft] = []
    for message in messages:
        lines = _content_lines(message.body)
        context: list[str] = []
        expect_you: bool = False
        for index, line in enumerate(lines):
            bullet = _BULLET.match(line)
            if bullet and (expect_you or _looks_actionable(bullet.group("body"))):
                _add_task(drafts, bullet.group("body"), "you", None, EvidenceType.explicit_request, Confidence.high, line, message, context)
                _collect_questions(question_drafts, line, message, message.addressee_name)
                continue
            expect_you = False
            if _INTRO.match(line):
                expect_you = True
                context.append(line)
                continue
            if _is_preamble(line, lines[index + 1 :]):
                context.append(line)
                continue
            if _consume_line(drafts, question_drafts, line, message, context):
                continue
            context.append(line)
            _collect_questions(question_drafts, line, message, message.addressee_name)

    drafts, duplicate_notes = _dedupe(drafts)
    result = Extraction()
    result.warnings.extend(duplicate_notes)
    task_index = 0
    commitment_index = 0
    for draft in drafts:
        if draft.commitment:
            commitment_index += 1
            result.commitments.append(_commitment(draft, commitment_index, received_at))
        else:
            task_index += 1
            result.tasks.append(_task(draft, task_index, result.warnings, received_at))
    result.questions = _questions(question_drafts)
    _link_questions(result.tasks, result.questions)
    _infer_dates(result.tasks)
    result.warnings.extend(_link_dependencies(result.tasks))
    _apply_status(messages, result.tasks, result.warnings)
    _break_cycles(result.tasks, result.warnings)
    return result


def _consume_line(drafts, question_drafts, line: str, message: EmailMessage, context: list[str]) -> bool:
    need_you = _NEED_YOU.match(line)
    if need_you:
        _add_task(drafts, need_you.group("task"), "you", None, EvidenceType.explicit_request, Confidence.high, line, message, context)
        _collect_questions(question_drafts, line, message, message.addressee_name)
        return True
    you = _YOU.match(line)
    if you:
        _add_task(drafts, you.group("task"), "you", None, EvidenceType.explicit_request, Confidence.high, line, message, context)
        _collect_questions(question_drafts, line, message, message.addressee_name)
        return True
    named = _NAMED.match(line)
    if named and named.group("name").split()[0].lower() not in {"could", "can", "would", "please", "we", "someone"}:
        _add_task(
            drafts,
            named.group("task"),
            "named",
            named.group("name"),
            EvidenceType.explicit_request,
            Confidence.high,
            line,
            message,
            context,
        )
        _collect_questions(question_drafts, line, message, named.group("name"))
        return True
    lets = _LETS.match(line)
    if lets:
        _add_task(drafts, lets.group("task"), "unassigned", None, EvidenceType.suggested_action, Confidence.medium, line, message, context)
        return True
    should = _SHOULD.match(line)
    if should:
        _add_task(
            drafts,
            should.group("task"),
            "unassigned",
            None,
            EvidenceType.suggested_action,
            Confidence.medium,
            line,
            message,
            context,
        )
        return True
    commitment = _COMMIT.match(line)
    if commitment:
        task_text = commitment.group("task")
        _add_task(
            drafts,
            task_text,
            "sender",
            message.sender_name,
            EvidenceType.commitment,
            Confidence.high,
            line,
            message,
            context,
            commitment=True,
        )
        return True
    need = _NEED.match(line)
    if need:
        _add_task(drafts, need.group("task"), "unassigned", None, EvidenceType.implied_action, Confidence.medium, line, message, context)
        return True
    implied = _IMPLIED.match(line)
    if implied:
        _add_task(drafts, line, "unassigned", None, EvidenceType.implied_action, Confidence.medium, line, message, context)
        return True
    return False


def _add_task(
    drafts: list[_Draft],
    task_text: str,
    owner_mode: str,
    owner_name: str | None,
    evidence_type: EvidenceType,
    confidence: Confidence,
    supporting_text: str,
    message: EmailMessage,
    context: list[str],
    commitment: bool = False,
) -> None:
    description, wording, hint = split_deadline(task_text)
    description = clean_description(description)
    if not description:
        return
    drafts.append(
        _Draft(
            description=description,
            owner_mode=owner_mode,
            owner_name=owner_name,
            wording=wording,
            hint=hint,
            evidence_type=evidence_type,
            confidence=confidence,
            supporting_text=supporting_text.strip(),
            message=message,
            preamble=" ".join(context),
            commitment=commitment,
        )
    )


def _task(draft: _Draft, index: int, warnings: list[str], received_at: datetime | None = None) -> Task:
    reference = _reference(draft.message, received_at)
    deadline = resolve_deadline(draft.wording, draft.hint, reference, draft.message.message_id)
    owner = _owner(draft, draft.message)
    dated = deadline.kind == DeadlineKind.explicit and deadline.precision in _DATED
    priority, explanation = _priority(draft.evidence_type, draft.supporting_text, draft.preamble, draft.message.body, dated)
    task_id = f"task-{index}"
    if deadline.kind == DeadlineKind.unresolved and deadline.original_wording:
        warnings.append(
            f"{task_id} has relative deadline \"{deadline.original_wording}\" and the message has no timestamp."
        )
    if (
        received_at is not None
        and not draft.message.date_iso
        and deadline.normalized_date
        and deadline.kind == DeadlineKind.explicit
    ):
        warnings.append(
            f"{task_id} normalized \"{deadline.original_wording}\" using the supplied received-at timestamp. "
            "The email did not include that calendar date."
        )
    if owner.ambiguous:
        warnings.append(f"{task_id} owner is ambiguous.")
    return Task(
        task_id=task_id,
        description=draft.description,
        owner=owner,
        deadline=deadline,
        priority=priority,
        priority_explanation=explanation,
        message_id=draft.message.message_id,
        supporting_text=draft.supporting_text,
        evidence_type=draft.evidence_type,
        confidence=draft.confidence,
    )


def _commitment(draft: _Draft, index: int, received_at: datetime | None = None) -> Commitment:
    reference = _reference(draft.message, received_at)
    deadline = None
    if draft.wording:
        deadline = resolve_deadline(draft.wording, draft.hint, reference, draft.message.message_id)
    return Commitment(
        commitment_id=f"commitment-{index}",
        description=draft.description,
        made_by=draft.message.sender_name,
        message_id=draft.message.message_id,
        supporting_text=draft.supporting_text,
        deadline=deadline,
    )


def _questions(drafts: list[_QuestionDraft]) -> list[Question]:
    questions: list[Question] = []
    seen: set[tuple[str, str]] = set()
    for draft in drafts:
        key = (draft.message.message_id, draft.original_wording.strip().lower())
        if key in seen:
            continue
        if draft.original_wording not in draft.message.body:
            continue
        seen.add(key)
        questions.append(
            Question(
                question_id=f"question-{len(questions) + 1}",
                text=draft.text,
                original_wording=draft.original_wording,
                message_id=draft.message.message_id,
                directed_to=draft.directed_to,
                kind=draft.kind,
            )
        )
    return questions


def _collect_questions(
    drafts: list[_QuestionDraft],
    line: str,
    message: EmailMessage,
    directed_to: str | None,
) -> None:
    confirm = re.search(r"confirm whether\s+(.+?)(?:\.|\?|$)", line, re.IGNORECASE)
    if confirm:
        clause = confirm.group(1).strip(" .")
        drafts.append(
            _QuestionDraft(
                text=_whether_question(clause),
                original_wording=line.strip(),
                message=message,
                directed_to=directed_to,
                kind="confirmation",
            )
        )
        return
    if "approve" in line.lower() and re.search(r"\b(please\s+)?approve\b|\bdo you approve\b", line, re.IGNORECASE):
        drafts.append(
            _QuestionDraft(
                text=line.strip(),
                original_wording=line.strip(),
                message=message,
                directed_to=directed_to,
                kind="approval",
            )
        )
        return
    if line.strip().endswith("?"):
        drafts.append(
            _QuestionDraft(
                text=line.strip(),
                original_wording=line.strip(),
                message=message,
                directed_to=directed_to,
                kind="question",
            )
        )
        return
    if _MISSING.search(line):
        drafts.append(
            _QuestionDraft(
                text=line.strip(),
                original_wording=line.strip(),
                message=message,
                directed_to=directed_to,
                kind="missing_information",
            )
        )


def _whether_question(clause: str) -> str:
    match = re.match(r"^(?P<subject>.+?)\s+is\s+(?P<rest>.+)$", clause, re.IGNORECASE)
    if match:
        return f"Is {match.group('subject')} {match.group('rest')}?"
    return f"Can you confirm whether {clause}?"


def _link_questions(tasks: list[Task], questions: list[Question]) -> None:
    for task in tasks:
        for question in questions:
            if question.message_id != task.message_id:
                continue
            if question.original_wording in task.supporting_text or len(tokens(question.text) & tokens(task.description)) >= 2:
                if question.question_id not in task.related_questions:
                    task.related_questions.append(question.question_id)


def _infer_dates(tasks: list[Task]) -> None:
    for task in tasks:
        wording = task.deadline.original_wording or ""
        if not wording.lower().startswith("the day before "):
            continue
        matches = [other for other in tasks if other.task_id != task.task_id and _event_match(wording, other)]
        if len(matches) != 1:
            continue
        anchor = matches[0].deadline.normalized_date
        if not anchor or matches[0].deadline.precision not in {DatePrecision.day, DatePrecision.time}:
            continue
        shifted = day_before(anchor)
        if not shifted:
            continue
        task.deadline = Deadline(
            original_wording=wording,
            normalized_date=shifted,
            precision=DatePrecision.day,
            confidence=Confidence.medium,
            kind=DeadlineKind.inferred,
            source_message_id=task.message_id,
            timezone=matches[0].deadline.timezone,
        )
        if matches[0].task_id not in task.dependencies:
            task.dependencies.append(matches[0].task_id)


def _link_dependencies(tasks: list[Task]) -> list[str]:
    warnings: list[str] = []
    grouped: dict[str, list[Task]] = {}
    for task in tasks:
        grouped.setdefault(task.message_id, []).append(task)
    for task in tasks:
        phrase = (task.deadline.original_wording or "").lower()
        if not phrase:
            continue
        earlier = [other for other in grouped.get(task.message_id, []) if _number(other.task_id) < _number(task.task_id)]
        if re.search(r"\b(these|those|the remaining|all|other)\b", phrase) and re.search(
            r"\b(items|tasks|deliverables|things|work)\b", phrase
        ):
            task.dependencies = [other.task_id for other in earlier]
            continue
        if task.dependencies:
            continue
        if phrase.startswith(("the day before", "the day after", "after ", "once ", "when ", "as soon as")):
            matches = [other for other in tasks if other.task_id != task.task_id and _event_match(phrase, other)]
            if len(matches) == 1:
                task.dependencies = [matches[0].task_id]
            elif len(matches) > 1:
                warnings.append(
                    f"{task.task_id} mentions \"{task.deadline.original_wording}\" but it matches more than one task, so no dependency was added."
                )
    return warnings


def _apply_status(messages: list[EmailMessage], tasks: list[Task], warnings: list[str]) -> None:
    order = {message.message_id: index for index, message in enumerate(messages)}
    before = {task.task_id: task.status for task in tasks}
    for message in messages:
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", message.body):
            sentence = sentence.strip()
            if not sentence:
                continue
            _mark_completed(sentence, message, tasks, order)
            _mark_blocked(sentence, message, tasks, order)
    for task in tasks:
        if task.status == before[task.task_id]:
            continue
        if task.status == TaskStatus.completed:
            warnings.append(
                f"{task.task_id} is marked completed from a later message. Confirm that before treating it as done."
            )
        elif task.status == TaskStatus.blocked:
            warnings.append(
                f"{task.task_id} is marked blocked from a later message. Confirm that before treating it as settled."
            )


def _mark_completed(sentence: str, message: EmailMessage, tasks: list[Task], order: dict[str, int]) -> None:
    if not _DONE.search(sentence):
        return
    ranked: list[tuple[int, Task]] = []
    for task in tasks:
        if order.get(task.message_id, 0) >= order.get(message.message_id, 0):
            continue
        score = len(tokens(sentence) & tokens(task.description))
        if score:
            ranked.append((score, task))
    if not ranked:
        return
    ranked.sort(key=lambda item: item[0], reverse=True)
    if len(ranked) > 1 and ranked[0][0] == ranked[1][0]:
        return
    ranked[0][1].status = TaskStatus.completed


def _mark_blocked(sentence: str, message: EmailMessage, tasks: list[Task], order: dict[str, int]) -> None:
    if not re.search(r"\b(?:blocked|waiting)\b", sentence, re.IGNORECASE) or not re.search(r"\buntil\b", sentence, re.IGNORECASE):
        return
    left, right = re.split(r"\buntil\b", sentence, maxsplit=1, flags=re.IGNORECASE)
    visible = [task for task in tasks if order.get(task.message_id, 0) <= order.get(message.message_id, 0)]
    subjects = [task for task in visible if _event_match(left, task)]
    events = [task for task in visible if _event_match(right, task)]
    if len(subjects) == 1 and len(events) == 1 and subjects[0].task_id != events[0].task_id:
        subjects[0].status = TaskStatus.blocked
        if events[0].task_id not in subjects[0].dependencies:
            subjects[0].dependencies.append(events[0].task_id)


def _break_cycles(tasks: list[Task], warnings: list[str]) -> None:
    guard = 0
    while _has_cycle({task.task_id: list(task.dependencies) for task in tasks}) and guard < 20:
        guard += 1
        for task in reversed(tasks):
            if task.dependencies and _has_cycle({item.task_id: list(item.dependencies) for item in tasks}):
                removed = task.dependencies.pop()
                warnings.append(f"Removed dependency {task.task_id} -> {removed} because it created a cycle.")
                break


def _event_match(phrase: str, task: Task) -> bool:
    overlap = tokens(phrase) & tokens(task.description)
    if len(overlap) >= 2:
        return True
    return any(len(word) >= 6 for word in overlap)


def _priority(
    evidence: EvidenceType,
    supporting: str,
    preamble: str,
    body: str,
    dated: bool,
) -> tuple[PriorityLevel, str]:
    low = _urgency_phrase(_LOW, supporting)
    if low:
        return PriorityLevel.low, f'The request says "{low}", so it stays low priority.'
    if evidence == EvidenceType.suggested_action:
        own = _urgency_phrase(_STRONG, supporting) or _urgency_phrase(_WEAK, supporting)
        if own:
            return PriorityLevel.high, f'The suggestion says "{own}". Priority comes from that wording.'
        return PriorityLevel.medium, "This is a suggestion, not a direct request. No urgency wording was applied."
    own = _urgency_phrase(_STRONG, supporting) or _urgency_phrase(_WEAK, supporting)
    if own:
        return (
            PriorityLevel.high,
            f'The request uses urgency language ("{own}"). The priority is based on that wording, not on the deadline alone.',
        )
    context_strong = _urgency_phrase(_STRONG, body)
    if context_strong and evidence == EvidenceType.explicit_request:
        return (
            PriorityLevel.high,
            f'The message says "{context_strong}". That urgency applies to this request, separate from any deadline.',
        )
    context_weak = _urgency_phrase(_WEAK, preamble)
    if context_weak and dated and evidence == EvidenceType.explicit_request:
        return (
            PriorityLevel.high,
            f'The message says "{context_weak}" ahead of this dated request. '
            "The deadline is stored on its own and is not itself the reason for high priority.",
        )
    if evidence == EvidenceType.explicit_request:
        return (
            PriorityLevel.medium,
            "This is an explicit request without urgency language. A deadline, when one is present, does not by itself raise the priority.",
        )
    if evidence == EvidenceType.implied_action:
        return PriorityLevel.medium, "This action is implied by the wording, and the message does not add an urgency marker."
    return PriorityLevel.unknown, "The message does not say how urgent this is."


def _urgency_phrase(pattern: re.Pattern[str], text: str) -> str | None:
    for match in pattern.finditer(text):
        prefix = text[max(0, match.start() - 16) : match.start()]
        if re.search(r"\b(not|never|no|n't)\s*$", prefix, re.IGNORECASE):
            continue
        if match.group(1).lower() == "must" and re.match(r"\s+not\b", text[match.end() : match.end() + 8], re.IGNORECASE):
            continue
        return match.group(1)
    return None


def _owner(draft: _Draft, message: EmailMessage) -> Owner:
    if draft.owner_mode == "named" and draft.owner_name:
        role = "team" if _is_team(draft.owner_name) else "named"
        return Owner(
            name=draft.owner_name,
            email=_email_for(message, draft.owner_name),
            role=role,  # type: ignore[arg-type]
            confidence=Confidence.high,
            ambiguous=False,
        )
    if draft.owner_mode == "you":
        if message.addressee_name and not message.addressee_ambiguous:
            return Owner(
                name=message.addressee_name,
                email=_email_for(message, message.addressee_name),
                role="recipient",
                confidence=Confidence.high,
                ambiguous=False,
            )
        if message.addressee_name and message.addressee_ambiguous:
            return Owner(
                name=message.addressee_name,
                email=_email_for(message, message.addressee_name),
                role="recipient",
                confidence=Confidence.medium,
                ambiguous=True,
            )
        return Owner(role="unassigned", confidence=Confidence.low, ambiguous=True)
    return Owner(role="unassigned", confidence=Confidence.medium, ambiguous=False)


def _is_team(name: str) -> bool:
    lowered = name.lower().strip()
    return lowered.endswith(" team") or lowered.endswith(" department") or lowered in _TEAMS


def _email_for(message: EmailMessage, name: str) -> str | None:
    for person in [*message.to, *message.cc]:
        if person.name and person.name.lower() == name.lower() and person.email:
            return person.email
    if message.sender_name and message.sender_name.lower() == name.lower():
        return message.sender_email
    return None


def _content_lines(body: str) -> list[str]:
    lines = []
    for raw in body.split("\n"):
        line = raw.strip()
        if not line or _GREETING.match(line):
            continue
        lines.append(line)
    return lines


def _looks_actionable(text: str) -> bool:
    description, wording, _hint = split_deadline(text)
    return bool(_IMPERATIVE.match(description) or _IMPERATIVE.match(text) or wording)


def _is_preamble(line: str, following: list[str]) -> bool:
    if not _NEED.match(line):
        return False
    return any(_INTRO.match(item) or _BULLET.match(item) or _NAMED.match(item) or _LETS.match(item) or re.search(r"\bplease\b", item, re.IGNORECASE) for item in following)


def _reference(message: EmailMessage, received_at: datetime | None = None) -> datetime | None:
    if message.date_iso:
        try:
            return datetime.fromisoformat(message.date_iso)
        except ValueError:
            pass
    return received_at


def _dedupe(drafts: list[_Draft]) -> tuple[list[_Draft], list[str]]:
    kept: list[_Draft] = []
    notes: list[str] = []
    for draft in drafts:
        earlier = next((item for item in kept if _same_action(draft, item)), None)
        if earlier is None:
            kept.append(draft)
            continue
        later = draft.wording or ""
        first = earlier.wording or ""
        if not draft.commitment and later.lower() != first.lower():
            notes.append(
                f"\"{earlier.description}\" is restated with deadline \"{later or 'no deadline'}\" "
                f"after \"{first or 'no deadline'}\". Neither date replaces the other."
            )
    return kept, notes


def _same_action(left: _Draft, right: _Draft) -> bool:
    if left.commitment != right.commitment:
        return False
    left_tokens = tokens(left.description)
    right_tokens = tokens(right.description)
    if not left_tokens or not right_tokens:
        return False
    overlap = len(left_tokens & right_tokens)
    return overlap / max(len(left_tokens), len(right_tokens)) >= 0.8


def _number(task_id: str) -> int:
    match = re.search(r"(\d+)$", task_id)
    return int(match.group(1)) if match else 0


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
