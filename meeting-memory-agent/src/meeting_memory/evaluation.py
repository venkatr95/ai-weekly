"""Score answers to the bundled questions."""

from __future__ import annotations

import json
from pathlib import Path

from meeting_memory.errors import InputError
from meeting_memory.pipeline import MeetingMemory
from meeting_memory.schemas import EvaluationReport, QuestionScore


def load_questions(path: Path) -> list[dict[str, object]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InputError(f"{path.name} is not valid JSON.") from exc
    if not isinstance(payload, list):
        raise InputError(f"{path.name} must contain a JSON list of questions.")
    return payload


def evaluate(memory: MeetingMemory, questions: list[dict[str, object]]) -> EvaluationReport:
    scores: list[QuestionScore] = []
    for index, spec in enumerate(questions, start=1):
        question = str(spec.get("question") or "").strip()
        if not question:
            raise InputError("Each evaluation question needs a question string.")
        answer = memory.ask(question)
        failures: list[str] = []
        expected_abstain = bool(spec.get("abstain", False))
        if answer.abstained != expected_abstain:
            failures.append(f"abstained={answer.abstained}, expected {expected_abstain}")
        text = answer.text.casefold()
        for needle in _strings(spec.get("answer_contains")):
            if needle.casefold() not in text:
                failures.append(f"answer missing {needle!r}")
        for needle in _strings(spec.get("answer_excludes")):
            if needle.casefold() in text:
                failures.append(f"answer unexpectedly contains {needle!r}")
        evidence_text = "\n".join(item.quote for item in answer.evidence).casefold()
        for needle in _strings(spec.get("evidence_contains")):
            if needle.casefold() not in evidence_text:
                failures.append(f"evidence missing {needle!r}")
        speaker = spec.get("speaker")
        if isinstance(speaker, str) and speaker:
            if not any((item.speaker or "").casefold() == speaker.casefold() for item in answer.evidence):
                failures.append(f"speaker {speaker!r} not in evidence")
        meeting = spec.get("meeting")
        if isinstance(meeting, str) and meeting:
            if not any(meeting.casefold() in item.meeting_name.casefold() for item in answer.evidence):
                failures.append(f"meeting {meeting!r} not in evidence")
        timestamp = spec.get("timestamp")
        if isinstance(timestamp, str) and timestamp:
            if not any(item.start == timestamp for item in answer.evidence):
                failures.append(f"timestamp {timestamp!r} not in evidence")
        scores.append(
            QuestionScore(
                id=str(spec.get("id") or index),
                question=question,
                passed=not failures,
                failures=failures,
            )
        )
    passed = sum(1 for score in scores if score.passed)
    return EvaluationReport(passed=passed, total=len(scores), scores=scores)


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]
