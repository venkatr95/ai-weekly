"""Calendar phrases found in meeting transcripts.

A month and day without a year uses the meeting date. The year is not invented
when the meeting has no date. A primary deadline that would fall before the
meeting moves to the next year. A deadline named as the previous promise
("instead of March 20", "from March 20") keeps the meeting year.

"Next week" is seven days after the meeting date. A bare weekday is the next
occurrence of that weekday, including the meeting day itself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

_MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_WEEKDAY = r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
_DAY = r"\d{1,2}(?:st|nd|rd|th)?"
_DATE = (
    rf"(?:\d{{4}}-\d{{2}}-\d{{2}}"
    rf"|{_MONTH}\.?\s+{_DAY}(?:,?\s+\d{{4}})?"
    rf"|{_DAY}\s+{_MONTH}\.?(?:,?\s+\d{{4}})?"
    rf"|next\s+{_WEEKDAY}"
    rf"|this\s+{_WEEKDAY}"
    rf"|{_WEEKDAY}"
    rf"|today|tomorrow|tonight|next week|end of (?:the )?week|this week)"
)
_BY = re.compile(
    rf"\b(?:no later than|due by|due on|due|before|by|on)\s+({_DATE})\b",
    re.IGNORECASE,
)
_INSTEAD = re.compile(rf"\binstead of\s+({_DATE})\b", re.IGNORECASE)
_FROM_TO = re.compile(rf"\bfrom\s+({_DATE})\s+to\s+({_DATE})\b", re.IGNORECASE)
_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_MONTH_DAY = re.compile(
    rf"^({_MONTH})\.?\s+({_DAY})(?:,?\s+(\d{{4}}))?$",
    re.IGNORECASE,
)
_DAY_MONTH = re.compile(
    rf"^({_DAY})\s+({_MONTH})\.?(?:,?\s+(\d{{4}}))?$",
    re.IGNORECASE,
)
_NEXT_WEEKDAY = re.compile(rf"^next\s+({_WEEKDAY})$", re.IGNORECASE)
_THIS_WEEKDAY = re.compile(rf"^(?:this\s+)?({_WEEKDAY})$", re.IGNORECASE)
_RELATIVE = re.compile(
    r"^(today|tomorrow|tonight|next week|end of (?:the )?week|this week)$",
    re.IGNORECASE,
)
_EVENT = re.compile(
    r"\b(?:before|after|until|by)\s+"
    r"((?:the\s+)?(?:next|this|upcoming)\s+[A-Za-z]+(?:\s+[A-Za-z]+)?)\b",
    re.IGNORECASE,
)
_CLOCK = re.compile(
    r"\b(?:by|at|before)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)|noon|midnight)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedDeadline:
    wording: str | None = None
    iso: str | None = None
    kind: str = "none"
    prior_wording: str | None = None
    prior_iso: str | None = None
    prior_kind: str = "none"

    @property
    def present(self) -> bool:
        return bool(self.wording or self.prior_wording)


def parse_meeting_date(value: str) -> str | None:
    text = re.sub(r"\s+", " ", value).strip().rstrip(".")
    resolved = _resolve_phrase(text, None, historical=False, allow_relative=False)
    if resolved is None:
        return None
    iso, kind = resolved
    if iso and kind == "explicit":
        return iso
    return None


def parse_deadlines(sentence: str, meeting_date: date | None) -> ParsedDeadline | None:
    from_to = _FROM_TO.search(sentence)
    if from_to:
        prior = _resolve_captured(from_to.group(1), meeting_date, historical=True)
        current = _resolve_captured(from_to.group(2), meeting_date, historical=False)
        return _pack(current, prior)
    by = _BY.search(sentence)
    instead = _INSTEAD.search(sentence)
    if not by and not instead:
        return _event_or_time(sentence)
    current = _resolve_captured(by.group(1), meeting_date, historical=False) if by else None
    prior = _resolve_captured(instead.group(1), meeting_date, historical=True) if instead else None
    packed = _pack(current, prior)
    if not packed.present:
        return _event_or_time(sentence)
    return packed


def _event_or_time(sentence: str) -> ParsedDeadline | None:
    event = _EVENT.search(sentence)
    if event:
        wording = re.sub(r"\s+", " ", event.group(1)).strip()
        return ParsedDeadline(wording=wording, iso=None, kind="event")
    clock = _CLOCK.search(sentence)
    if clock:
        wording = re.sub(r"\s+", " ", clock.group(1)).strip()
        return ParsedDeadline(wording=wording, iso=None, kind="time")
    return None


def _pack(
    current: tuple[str, str | None, str] | None,
    prior: tuple[str, str | None, str] | None,
) -> ParsedDeadline:
    wording, iso, kind = current if current else (None, None, "none")
    prior_wording, prior_iso, prior_kind = prior if prior else (None, None, "none")
    return ParsedDeadline(
        wording=wording,
        iso=iso,
        kind=kind if wording else "none",
        prior_wording=prior_wording,
        prior_iso=prior_iso,
        prior_kind=prior_kind if prior_wording else "none",
    )


def _resolve_captured(
    phrase: str,
    meeting_date: date | None,
    *,
    historical: bool,
) -> tuple[str, str | None, str] | None:
    cleaned = re.sub(r"\s+", " ", phrase).strip()
    resolved = _resolve_phrase(cleaned, meeting_date, historical=historical, allow_relative=True)
    if resolved is None:
        return cleaned, None, "unresolved"
    iso, kind = resolved
    return cleaned, iso, kind


def _resolve_phrase(
    phrase: str,
    meeting_date: date | None,
    *,
    historical: bool,
    allow_relative: bool,
) -> tuple[str | None, str] | None:
    iso_match = _ISO.fullmatch(phrase)
    if iso_match:
        parsed = _safe_date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
        if parsed is None:
            return None
        return parsed.isoformat(), "explicit"

    month_day = _month_day_parts(phrase)
    if month_day is not None:
        month_name, day_token, year_text = month_day
        month = MONTHS[month_name.lower().rstrip(".")]
        day = _day_number(day_token)
        if year_text:
            parsed = _safe_date(int(year_text), month, day)
            if parsed is None:
                return None
            return parsed.isoformat(), "explicit"
        if meeting_date is None:
            return None, "unresolved"
        parsed = _safe_date(meeting_date.year, month, day)
        if parsed is None:
            return None, "unresolved"
        if not historical and parsed < meeting_date:
            parsed = _safe_date(meeting_date.year + 1, month, day)
            if parsed is None:
                return None, "unresolved"
        return parsed.isoformat(), "explicit"

    if not allow_relative:
        return None

    next_weekday = _NEXT_WEEKDAY.fullmatch(phrase)
    if next_weekday:
        if meeting_date is None:
            return None, "unresolved"
        target = WEEKDAYS[next_weekday.group(1).lower()]
        delta = (target - meeting_date.weekday()) % 7
        delta = 7 if delta == 0 else delta + 7
        return (meeting_date + timedelta(days=delta)).isoformat(), "relative"

    weekday = _THIS_WEEKDAY.fullmatch(phrase)
    if weekday:
        if meeting_date is None:
            return None, "unresolved"
        target = WEEKDAYS[weekday.group(1).lower()]
        delta = (target - meeting_date.weekday()) % 7
        return (meeting_date + timedelta(days=delta)).isoformat(), "relative"

    relative = _RELATIVE.fullmatch(phrase)
    if relative:
        if meeting_date is None:
            return None, "unresolved"
        label = re.sub(r"\s+", " ", relative.group(1).lower())
        if label in {"today", "tonight", "this week"}:
            return meeting_date.isoformat(), "relative"
        if label == "tomorrow":
            return (meeting_date + timedelta(days=1)).isoformat(), "relative"
        if label == "next week":
            return (meeting_date + timedelta(days=7)).isoformat(), "relative"
        # "end of the week" is the Friday of the meeting week, or the next Friday.
        delta = (WEEKDAYS["friday"] - meeting_date.weekday()) % 7
        return (meeting_date + timedelta(days=delta)).isoformat(), "relative"
    return None


def _month_day_parts(phrase: str) -> tuple[str, str, str | None] | None:
    match = _MONTH_DAY.fullmatch(phrase)
    if match:
        return match.group(1), match.group(2), match.group(3)
    return _swapped_day_month(phrase)


def _swapped_day_month(phrase: str) -> tuple[str, str, str | None] | None:
    match = _DAY_MONTH.fullmatch(phrase)
    if not match:
        return None
    return match.group(2), match.group(1), match.group(3)


def _day_number(token: str) -> int:
    return int(re.sub(r"(?:st|nd|rd|th)$", "", token, flags=re.IGNORECASE))


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None
