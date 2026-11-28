"""Drop citations that are not stored transcript segments.

A quote must be an exact substring of an utterance in the cited meeting.
When the citation has a timestamp, that timestamp must be the utterance's
timestamp. Missing timestamps stay missing. This module never fills one in.
"""

from __future__ import annotations

from meeting_memory.schemas import Answer, Evidence, Meeting


def validate_answer(answer: Answer, meetings: list[Meeting]) -> Answer:
    if answer.abstained or not answer.evidence:
        return answer
    by_id = {meeting.meeting_id: meeting for meeting in meetings}
    kept = [item for item in answer.evidence if _supports(by_id.get(item.meeting_id), item)]
    if len(kept) == len(answer.evidence):
        return answer
    if not kept:
        return Answer(
            question=answer.question,
            abstained=True,
            reason="invalid_citations",
            text="The drafted citations do not match a stored transcript segment.",
            evidence=[],
            items=[],
            related_commitments=[],
            unresolved_questions=[],
            conflicts=[],
        )
    return answer.model_copy(update={"evidence": kept})


def _supports(meeting: Meeting | None, evidence: Evidence) -> bool:
    if meeting is None:
        return False
    for utterance in meeting.utterances:
        if evidence.quote not in utterance.text:
            continue
        if evidence.start is not None and evidence.start != utterance.start:
            continue
        if evidence.end is not None and evidence.end != utterance.end:
            continue
        if evidence.speaker and utterance.speaker and evidence.speaker != utterance.speaker:
            continue
        if evidence.line_start is not None and utterance.line_start is not None:
            if evidence.start is None and evidence.line_start != utterance.line_start:
                continue
        return True
    return False
