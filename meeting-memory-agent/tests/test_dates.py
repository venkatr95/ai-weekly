from datetime import date, timedelta

from meeting_memory.dates import parse_deadlines


def test_month_day_uses_the_meeting_year():
    parsed = parse_deadlines("I will deliver the API by March 20.", date(2026, 3, 4))
    assert parsed is not None
    assert parsed.iso == "2026-03-20"
    assert parsed.kind == "explicit"


def test_past_month_day_moves_to_next_year():
    parsed = parse_deadlines("Send the notes by March 2.", date(2026, 3, 18))
    assert parsed is not None
    assert parsed.iso == "2027-03-02"


def test_instead_of_keeps_the_meeting_year_for_an_earlier_day():
    parsed = parse_deadlines(
        "I will deliver the API by March 27 instead of March 20.",
        date(2026, 3, 21),
    )
    assert parsed is not None
    assert parsed.iso == "2026-03-27"
    assert parsed.prior_iso == "2026-03-20"


def test_weekday_without_a_meeting_date_stays_unresolved():
    parsed = parse_deadlines("I will send the notes by Friday.", None)
    assert parsed is not None
    assert parsed.iso is None
    assert parsed.kind == "unresolved"
    assert parsed.wording.lower() == "friday"


def test_month_day_without_a_meeting_date_keeps_the_wording():
    parsed = parse_deadlines("I will deliver the API by December 5.", None)
    assert parsed is not None
    assert parsed.iso is None
    assert parsed.kind == "unresolved"
    assert parsed.wording.lower() == "december 5"


def test_event_and_clock_deadlines_stay_unnormalized():
    event = parse_deadlines("Ship the build before the next release.", date(2026, 11, 20))
    clock = parse_deadlines("I will send the notes by 5pm.", date(2026, 11, 20))
    assert event is not None and event.kind == "event" and event.iso is None
    assert "next release" in (event.wording or "")
    assert clock is not None and clock.kind == "time" and clock.iso is None
    assert clock.wording is not None and "5pm" in clock.wording.lower()


def test_friday_is_the_next_friday_including_the_meeting_day():
    meeting = date(2026, 3, 4)
    parsed = parse_deadlines("I will send the notes by Friday.", meeting)
    assert parsed is not None
    assert parsed.kind == "relative"
    expected = meeting + timedelta(days=(4 - meeting.weekday()) % 7)
    assert parsed.iso == expected.isoformat()
    assert date.fromisoformat(parsed.iso).weekday() == 4


def test_next_week_is_seven_days_after_the_meeting():
    parsed = parse_deadlines("I will send the notes by next week.", date(2026, 3, 4))
    assert parsed is not None
    assert parsed.iso == "2026-03-11"
    assert parsed.kind == "relative"


def test_a_stated_year_is_not_rewritten():
    parsed = parse_deadlines("The review is due on March 20, 2025.", date(2026, 3, 4))
    assert parsed is not None
    assert parsed.iso == "2025-03-20"
    assert parsed.kind == "explicit"
