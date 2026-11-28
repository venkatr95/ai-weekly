"""Markdown and JSON views of answers, summaries, and evaluations."""

from __future__ import annotations

import json

from meeting_memory.schemas import (
    Answer,
    EvaluationReport,
    Evidence,
    IngestReport,
    Meeting,
    MeetingSummary,
    MemoryItem,
)


def format_evidence(evidence: Evidence) -> str:
    when = evidence.start or (f"line {evidence.line_start}" if evidence.line_start else "time not recorded")
    speaker = evidence.speaker or "Unknown speaker"
    held = evidence.held_on or "date not recorded"
    return f'{evidence.meeting_name} ({held}) — {speaker} at {when} — "{evidence.quote}"'


def render_answer_markdown(answer: Answer) -> str:
    lines = ["## Answer", "", answer.text, "", "## Evidence", ""]
    if not answer.evidence:
        lines.append("No supporting transcript passage was cited.")
    else:
        lines.extend(f"- {format_evidence(item)}" for item in answer.evidence)
    if answer.related_commitments:
        lines.extend(["", "## Related commitments", ""])
        for item in answer.related_commitments:
            owner = item.owner or "Unassigned"
            deadline = item.deadline or "not specified"
            lines.append(f"- {owner}: {item.action}. Deadline: {deadline}.")
    if answer.unresolved_questions:
        lines.extend(["", "## Unresolved questions", ""])
        lines.extend(f"- {question}" for question in answer.unresolved_questions)
    if answer.conflicts:
        lines.extend(["", "## Conflicts", ""])
        lines.extend(f"- {item}" for item in answer.conflicts)
    return "\n".join(lines).rstrip() + "\n"


def render_answer_json(answer: Answer) -> str:
    payload = answer.model_dump()
    payload["answer"] = answer.text
    payload["abstained"] = answer.abstained
    for item in payload["evidence"]:
        item["meeting_title"] = item.get("meeting_name")
        item["timestamp_start"] = item.get("start_seconds")
        item["timestamp_end"] = item.get("end_seconds")
    return json.dumps(payload, indent=2)


def build_summary(meeting: Meeting, items: list[MemoryItem]) -> MeetingSummary:
    mine = [item for item in items if item.meeting_id == meeting.meeting_id and item.kind != "status"]
    mine.sort(key=lambda item: (item.utterance_index, item.item_id))
    decisions = [item for item in mine if item.kind == "decision"]
    commitments = [item for item in mine if item.kind == "commitment"]
    tasks = [item for item in mine if item.kind == "task"]
    questions = [item for item in mine if item.kind == "question"]
    participants = ", ".join(meeting.participants) if meeting.participants else "not recorded"
    lines = [
        f"# {meeting.name}",
        "",
        f"Held: {meeting.held_on or 'date not recorded'}",
        f"Participants: {participants}",
        "",
        "## Decisions",
        "",
    ]
    lines.extend(_item_lines(decisions, "Explicit decision"))
    lines.extend(["", "## Commitments", ""])
    lines.extend(_item_lines(commitments, "Explicit commitment"))
    lines.extend(["", "## Tasks", ""])
    lines.extend(_item_lines(tasks, "Task"))
    lines.extend(["", "## Questions", ""])
    lines.extend(_item_lines(questions, "Question"))
    markdown = "\n".join(lines).rstrip() + "\n"
    return MeetingSummary(
        meeting_id=meeting.meeting_id,
        name=meeting.name,
        held_on=meeting.held_on,
        participants=list(meeting.participants),
        decisions=decisions,
        commitments=commitments,
        tasks=tasks,
        questions=questions,
        markdown=markdown,
    )


def render_summary_json(summary: MeetingSummary) -> str:
    return summary.model_dump_json(indent=2)


def render_ingest(report: IngestReport) -> str:
    lines = [
        f"Indexed {report.meetings_added} meetings ({report.meetings_total} stored).",
        f"Index: {report.index_dir}",
    ]
    for name in report.files_needs_transcription:
        lines.append(f"Needs transcription: {name}")
    for name in report.files_skipped:
        lines.append(f"Skipped: {name}")
    for name in report.files_failed:
        lines.append(f"Failed: {name}")
    for warning in report.warnings:
        lines.append(f"Warning: {warning}")
    return "\n".join(lines)


def render_evaluation(report: EvaluationReport) -> str:
    lines = [f"Passed {report.passed} of {report.total} questions."]
    for score in report.scores:
        mark = "PASS" if score.passed else "FAIL"
        lines.append(f"{mark} {score.id}: {score.question}")
        for failure in score.failures:
            lines.append(f"  - {failure}")
    return "\n".join(lines)


def _item_lines(items: list[MemoryItem], label: str) -> list[str]:
    if not items:
        return ["None recorded."]
    lines = []
    for item in items:
        owner = f"{item.owner}: " if item.owner else ""
        if item.status == "unconfirmed":
            kind = "Unconfirmed offer"
        elif item.evidence_type == "inferred":
            kind = "Inferred responsibility"
        elif item.decision_status == "proposed":
            kind = "Proposed decision"
        elif item.decision_status == "rejected":
            kind = "Rejected proposal"
        elif item.decision_status == "deferred":
            kind = "Deferred decision"
        else:
            kind = label
        deadline = f" Deadline: {item.deadline_iso}." if item.deadline_iso else ""
        lines.append(
            f"- {kind} ({item.status}). {owner}{item.text}{deadline} {format_evidence(item.evidence)}"
        )
    return lines
