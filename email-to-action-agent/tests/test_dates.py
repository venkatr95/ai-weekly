"""Calendar resolution stays inside what the email actually said."""

from datetime import datetime, timedelta, timezone

from email_to_action.dates import resolve_deadline, split_deadline

REF = datetime(2026, 11, 2, 9, 0, tzinfo=timezone(timedelta(hours=-5)))


def test_split_keeps_the_action_and_the_date_phrase():
    description, wording, hint = split_deadline(
        "Send the final product screenshots to the marketing team by November 7."
    )
    assert description == "Send the final product screenshots to the marketing team"
    assert wording == "November 7"
    assert hint == "date"


def test_split_event_deadline_from_the_end_of_the_sentence():
    description, wording, hint = split_deadline(
        "Schedule a final review meeting once these items are complete."
    )
    assert description == "Schedule a final review meeting"
    assert wording == "once these items are complete"
    assert hint == "event"


def test_confirmation_without_a_date_stays_whole():
    description, wording, hint = split_deadline("Confirm whether the pricing page is ready")
    assert wording is None
    assert hint == "none"
    assert "pricing page" in description


def test_relative_date_without_a_timestamp_is_unresolved():
    deadline = resolve_deadline("Friday", "date", None, "message-1")
    assert deadline.kind.value == "unresolved"
    assert deadline.normalized_date is None
    assert deadline.confidence.value == "low"


def test_friday_uses_the_message_timestamp():
    deadline = resolve_deadline("Friday", "date", REF, "message-1")
    assert deadline.kind.value == "explicit"
    assert deadline.normalized_date == "2026-11-06"
    assert deadline.precision.value == "day"


def test_next_friday_skips_the_coming_friday():
    deadline = resolve_deadline("next Friday", "date", REF, "message-1")
    assert deadline.normalized_date == "2026-11-13"


def test_tomorrow_in_days_and_end_of_day():
    assert resolve_deadline("tomorrow", "date", REF, "message-1").normalized_date == "2026-11-03"
    assert resolve_deadline("in 3 days", "date", REF, "message-1").normalized_date == "2026-11-05"
    end_of_day = resolve_deadline("end of day", "date", REF, "message-1")
    assert end_of_day.normalized_date == "2026-11-02"
    assert end_of_day.time is None
    assert end_of_day.confidence.value == "medium"


def test_month_day_uses_the_message_year_and_rolls_forward():
    dated = resolve_deadline("November 10", "date", REF, "message-1")
    assert dated.normalized_date == "2026-11-10"
    december = datetime(2026, 12, 20, 9, 0)
    rolled = resolve_deadline("January 5", "date", december, "message-1")
    assert rolled.normalized_date == "2027-01-05"


def test_month_day_without_a_year_or_timestamp_is_not_invented():
    deadline = resolve_deadline("November 10", "date", None, "message-1")
    assert deadline.kind.value == "explicit"
    assert deadline.normalized_date is None
    assert deadline.precision.value == "day"


def test_ambiguous_numeric_date_is_not_normalized():
    deadline = resolve_deadline("02/03/2026", "date", REF, "message-1")
    assert deadline.normalized_date is None
    assert deadline.confidence.value == "low"


def test_unambiguous_numeric_date_and_range():
    assert resolve_deadline("13/02/2026", "date", None, "message-1").normalized_date == "2026-02-13"
    ranged = resolve_deadline("between November 10 and November 12", "date", REF, "message-1")
    assert ranged.normalized_date == "2026-11-10/2026-11-12"
    assert ranged.precision.value == "range"


def test_clock_time_uses_the_message_day_and_keeps_the_zone_label():
    deadline = resolve_deadline("3pm ET", "date", REF, "message-1")
    assert deadline.normalized_date == "2026-11-02"
    assert deadline.time == "15:00"
    assert deadline.timezone == "ET"
    unresolved = resolve_deadline("3pm ET", "date", None, "message-1")
    assert unresolved.kind.value == "unresolved"
    assert unresolved.normalized_date is None
    assert unresolved.time == "15:00"


def test_after_a_named_day_does_not_pretend_the_day_is_the_deadline():
    deadline = resolve_deadline("after Friday", "date", REF, "message-1")
    assert deadline.normalized_date is None
    assert deadline.original_wording == "after Friday"
    assert deadline.kind.value == "explicit"
