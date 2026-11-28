from meeting_memory.evidence_validator import validate_answer
from meeting_memory.schemas import Answer, Evidence, Meeting, Utterance


def _meeting() -> Meeting:
    return Meeting(
        meeting_id="mtg_test",
        name="API Integration Planning",
        source_path="planning.txt",
        transcript_path="planning.txt",
        origin="transcript",
        utterances=[
            Utterance(
                utterance_id="utt_1",
                index=0,
                speaker="Alex",
                start="00:02:38",
                start_seconds=158.0,
                text="Yes, I'll deliver the API implementation by December 5.",
                line_start=8,
            )
        ],
    )


def test_validator_keeps_a_real_quote_and_drops_an_invented_one():
    meeting = _meeting()
    good = Evidence(
        meeting_id=meeting.meeting_id,
        meeting_name=meeting.name,
        speaker="Alex",
        start="00:02:38",
        start_seconds=158.0,
        quote="Yes, I'll deliver the API implementation by December 5.",
        source_path=meeting.source_path,
        line_start=8,
    )
    invented = good.model_copy(update={"quote": "Alex promised delivery on December 1.", "start": "00:09:00"})
    answer = Answer(question="Who agreed?", abstained=False, text="Invented.", evidence=[invented])
    validated = validate_answer(answer, [meeting])
    assert validated.abstained is True
    assert validated.reason == "invalid_citations"
    assert validated.evidence == []

    kept = validate_answer(
        Answer(question="Who agreed?", abstained=False, text="Alex agreed.", evidence=[good]),
        [meeting],
    )
    assert kept.abstained is False
    assert kept.evidence[0].quote == good.quote
    assert kept.evidence[0].end is None
