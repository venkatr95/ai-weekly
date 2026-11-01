"""Deadline phrases and calendar resolution.

Relative dates use the message timestamp. Without one, they stay unresolved.
A calendar year is not invented for a month and day when the message has no date.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from email_to_action.schemas import Confidence, DatePrecision, Deadline, DeadlineKind

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
_CLOCK = r"(?:\d{1,2}(?::\d{2})?\s*(?:am|pm)|(?:[01]?\d|2[0-3]):[0-5]\d)"
_TZ = r"(?:UTC|GMT|ET|EST|EDT|PT|PST|PDT|CT|CST|CDT|MT|MST|MDT|[+-]\d{2}:?\d{2})"
_TIME = rf"(?:at\s+)?{_CLOCK}(?:\s+{_TZ})?"
_RELATIVE = (
    rf"(?:today|tomorrow|tonight|eod|cob|end of (?:the )?day|end of (?:the )?week|"
    rf"next week|next month|this week|in \d+ (?:days?|weeks?|hours?)|"
    rf"(?:next|this)\s+{_WEEKDAY}|{_WEEKDAY})"
)
_MONTH_DAY = rf"{_MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?"
_DAY_MONTH = rf"\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTH}\.?(?:,?\s+\d{{4}})?"
_ISO = r"\d{4}-\d{2}-\d{2}(?:[T ](?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?(?:Z|[+-]\d{2}:?\d{2})?)?"
_NUMERIC = r"\d{1,2}/\d{1,2}/\d{2,4}"
_DATE_ATOM = rf"(?:{_ISO}|{_MONTH_DAY}|{_DAY_MONTH}|{_NUMERIC}|{_RELATIVE}|{_TIME})"
_RANGE = (
    rf"(?:between\s+{_DATE_ATOM}\s+and\s+{_DATE_ATOM}|"
    rf"{_MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?\s*[-–]\s*\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?)"
)
_DATE_SUFFIX = re.compile(rf"^(?:{_RANGE}|{_DATE_ATOM})(?:\s+{_TIME})?$", re.IGNORECASE)
_WINDOWS = re.compile(r"^(?:next week|next month|this week|end of (?:the )?week)$", re.IGNORECASE)
_RELATIVE_CORE = re.compile(
    rf"^(?:today|tomorrow|tonight|eod|cob|end of (?:the )?day|end of (?:the )?week|"
    rf"next week|next month|this week|in \d+ (?:days?|weeks?|hours?)|"
    rf"(?:next|this)\s+{_WEEKDAY}|{_WEEKDAY})$",
    re.IGNORECASE,
)
_PREFIXES = ("no later than", "due by", "due on", "due", "before", "by", "on", "after")
_EVENT_LEADS = ("the day before", "the day after", "as soon as", "once", "when", "after")
_KEEP_RELATION = {"after"}


def month_number(token: str) -> int | None:
    return MONTHS.get(token.lower().rstrip("."))


def split_deadline(text: str) -> tuple[str, str | None, str]:
    """Return the task text, the deadline wording, and 'date', 'event', or 'none'."""

    stripped = re.sub(r"\s+", " ", text).strip().rstrip(".?!")
    if not stripped:
        return "", None, "none"

    date_hit: tuple[str, str, int] | None = None
    for prefix in _PREFIXES:
        for match in re.finditer(rf"(?:^|\s)({re.escape(prefix)})\s+", stripped, re.IGNORECASE):
            suffix = stripped[match.end() :].strip()
            if not suffix or not _DATE_SUFFIX.fullmatch(suffix):
                continue
            body = stripped[: match.start(1)].strip(" ,")
            if not body:
                continue
            shown = suffix if prefix.lower() not in _KEEP_RELATION else f"{match.group(1)} {suffix}"
            if date_hit is None or match.start(1) >= date_hit[2]:
                date_hit = (body, shown, match.start(1))

    event_hit: tuple[str, str, int] | None = None
    for lead in _EVENT_LEADS:
        for match in re.finditer(rf"\b{re.escape(lead)}\b", stripped, re.IGNORECASE):
            tail = stripped[match.end() :].strip()
            body = stripped[: match.start()].strip(" ,")
            if not body or not tail:
                continue
            if lead in {"after", "before"} and _DATE_SUFFIX.fullmatch(tail):
                continue
            phrase = stripped[match.start() :].strip()
            if event_hit is None or match.start() >= event_hit[2]:
                event_hit = (body, phrase, match.start())

    if date_hit and event_hit:
        chosen = date_hit if date_hit[2] >= event_hit[2] else event_hit
        hint = "date" if chosen is date_hit else "event"
        return chosen[0], chosen[1], hint
    if date_hit:
        return date_hit[0], date_hit[1], "date"
    if event_hit:
        return event_hit[0], event_hit[1], "event"
    return stripped, None, "none"


def resolve_deadline(
    wording: str | None,
    hint: str,
    reference: datetime | None,
    message_id: str,
) -> Deadline:
    if not wording or hint == "none":
        return Deadline(
            kind=DeadlineKind.none,
            precision=DatePrecision.none,
            confidence=Confidence.medium,
            source_message_id=message_id,
        )
    if hint == "event":
        return Deadline(
            original_wording=wording,
            kind=DeadlineKind.explicit,
            precision=DatePrecision.event,
            confidence=Confidence.high,
            source_message_id=message_id,
        )

    relation, body = _relation(wording)
    _head, clock, zone = _peel_clock(body)
    if not _head and clock and reference is None:
        return Deadline(
            original_wording=wording,
            time=clock,
            timezone=zone,
            kind=DeadlineKind.unresolved,
            precision=DatePrecision.time,
            confidence=Confidence.low,
            source_message_id=message_id,
        )
    relative = _is_relative(body)
    if relation == "after":
        if relative and reference is None:
            return _unresolved(wording, message_id)
        return Deadline(
            original_wording=wording,
            kind=DeadlineKind.explicit,
            precision=DatePrecision.relative,
            confidence=Confidence.medium,
            source_message_id=message_id,
        )
    if relative and reference is None:
        return _unresolved(wording, message_id)
    if _WINDOWS.fullmatch(body):
        if reference is None:
            return _unresolved(wording, message_id)
        return Deadline(
            original_wording=wording,
            kind=DeadlineKind.explicit,
            precision=DatePrecision.relative,
            confidence=Confidence.medium,
            source_message_id=message_id,
        )

    date_text, clock, zone = _peel_clock(body)
    parsed = _parse_when(date_text, reference, clock, zone)
    if parsed is None:
        precision = DatePrecision.relative if relative else DatePrecision.day
        return Deadline(
            original_wording=wording,
            kind=DeadlineKind.explicit,
            precision=precision,
            confidence=Confidence.medium,
            source_message_id=message_id,
        )
    normalized, resolved_clock, resolved_zone, precision, confidence = parsed
    return Deadline(
        original_wording=wording,
        normalized_date=normalized,
        time=resolved_clock,
        timezone=resolved_zone if normalized else None,
        precision=precision,
        confidence=confidence,
        kind=DeadlineKind.explicit,
        source_message_id=message_id,
    )


def day_before(normalized: str) -> str | None:
    try:
        anchor = datetime.fromisoformat(normalized[:10]).date()
    except ValueError:
        return None
    return (anchor - timedelta(days=1)).isoformat()


def _unresolved(wording: str, message_id: str) -> Deadline:
    return Deadline(
        original_wording=wording,
        kind=DeadlineKind.unresolved,
        precision=DatePrecision.relative,
        confidence=Confidence.low,
        source_message_id=message_id,
    )


def _relation(wording: str) -> tuple[str, str]:
    for prefix in ("no later than", "due by", "due on", "due", "before", "by", "on", "after"):
        if wording.lower().startswith(prefix + " "):
            return prefix, wording[len(prefix) :].strip()
    return "on", wording.strip()


def _is_relative(phrase: str) -> bool:
    head, _clock, _zone = _peel_clock(phrase)
    return bool(_RELATIVE_CORE.fullmatch(head if head else phrase))


def _peel_clock(phrase: str) -> tuple[str, str | None, str | None]:
    match = re.search(rf"(?:\bat\s+)?(?P<clock>{_CLOCK})(?:\s+(?P<tz>{_TZ}))?\s*$", phrase.strip(), re.IGNORECASE)
    if not match:
        return phrase.strip(), None, None
    head = phrase.strip()[: match.start()].strip()
    clock = _normalize_clock(match.group("clock"))
    zone = match.group("tz").upper() if match.group("tz") else None
    if not head:
        return "", clock, zone
    if _DATE_SUFFIX.fullmatch(head) or _RELATIVE_CORE.fullmatch(head):
        return head, clock, zone
    return phrase.strip(), None, None


def _parse_when(
    phrase: str,
    reference: datetime | None,
    clock: str | None,
    zone: str | None,
) -> tuple[str | None, str | None, str | None, DatePrecision, Confidence] | None:
    text = phrase.strip()
    if not text:
        if clock and reference is not None:
            return reference.date().isoformat(), clock, zone or _offset(reference), DatePrecision.time, Confidence.medium
        return None

    hours = re.fullmatch(r"in\s+(\d+)\s+hours?", text, re.IGNORECASE)
    if hours and reference is not None:
        target = reference + timedelta(hours=int(hours.group(1)))
        return target.isoformat(), target.strftime("%H:%M"), zone or _offset(reference), DatePrecision.time, Confidence.high

    counted = re.fullmatch(r"in\s+(\d+)\s+(days?|weeks?)", text, re.IGNORECASE)
    if counted and reference is not None:
        amount = int(counted.group(1))
        if counted.group(2).lower().startswith("week"):
            amount *= 7
        target = (reference + timedelta(days=amount)).date().isoformat()
        return target, clock, zone or _offset(reference), DatePrecision.day, Confidence.medium

    named = text.lower()
    if named in {"today", "tonight", "eod", "cob"} or re.fullmatch(r"end of (?:the )?day", named):
        if reference is None:
            return None
        precision = DatePrecision.time if named == "tonight" or clock else DatePrecision.day
        confidence = Confidence.high if named in {"today", "tonight"} else Confidence.medium
        return reference.date().isoformat(), clock, zone or _offset(reference), precision, confidence
    if named == "tomorrow" and reference is not None:
        target = (reference + timedelta(days=1)).date().isoformat()
        precision = DatePrecision.time if clock else DatePrecision.day
        return target, clock, zone or _offset(reference), precision, Confidence.high

    weekday = _weekday_date(text, reference)
    if weekday and reference is not None:
        precision = DatePrecision.time if clock else DatePrecision.day
        return weekday, clock, zone or _offset(reference), precision, Confidence.high

    ranged = _parse_range(text, reference)
    if ranged is not None:
        return ranged

    iso = _parse_iso(text)
    if iso is not None:
        normalized, iso_clock = iso
        return normalized, clock or iso_clock, zone or _offset(reference), DatePrecision.time if (clock or iso_clock) else DatePrecision.day, Confidence.high

    month_day = _parse_month_day(text, reference)
    if month_day is not None:
        normalized, confidence = month_day
        precision = DatePrecision.time if clock else DatePrecision.day
        return normalized, clock, (zone or _offset(reference)) if normalized else None, precision, confidence

    numeric = _parse_numeric(text)
    if numeric is not None:
        normalized, confidence = numeric
        if normalized is None:
            return None, clock, zone, DatePrecision.day, Confidence.low
        return normalized, clock, zone or _offset(reference), DatePrecision.day, confidence
    return None


def _weekday_date(text: str, reference: datetime | None) -> str | None:
    if reference is None:
        return None
    match = re.fullmatch(rf"(?:(?P<which>next|this)\s+)?(?P<day>{_WEEKDAY})", text.strip(), re.IGNORECASE)
    if not match:
        return None
    target = WEEKDAYS[match.group("day").lower()]
    delta = (target - reference.weekday()) % 7
    if (match.group("which") or "").lower() == "next":
        delta = 7 if delta == 0 else delta + 7
    return (reference + timedelta(days=delta)).date().isoformat()


def _parse_iso(text: str) -> tuple[str, str | None] | None:
    if not re.fullmatch(_ISO, text, re.IGNORECASE):
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    clock = parsed.strftime("%H:%M") if re.search(r"[T ]\d{2}:\d{2}", text) else None
    return parsed.date().isoformat(), clock


def _parse_month_day(text: str, reference: datetime | None) -> tuple[str | None, Confidence] | None:
    match = re.fullmatch(
        rf"(?P<mon>{_MONTH})\.?\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(?P<year>\d{{4}}))?",
        text.strip(),
        re.IGNORECASE,
    )
    if not match:
        match = re.fullmatch(
            rf"(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\s+(?P<mon>{_MONTH})\.?(?:,?\s+(?P<year>\d{{4}}))?",
            text.strip(),
            re.IGNORECASE,
        )
    if not match:
        return None
    month = month_number(match.group("mon"))
    if month is None:
        return None
    day = int(match.group("day"))
    year = int(match.group("year")) if match.group("year") else None
    if year is None and reference is None:
        return None, Confidence.medium
    normalized = _with_year(month, day, year, reference)
    if normalized is None:
        return None, Confidence.medium
    confidence = Confidence.high if year or reference is not None else Confidence.medium
    return normalized, confidence


def _parse_numeric(text: str) -> tuple[str | None, Confidence] | None:
    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", text.strip())
    if not match:
        return None
    first = int(match.group(1))
    second = int(match.group(2))
    year = int(match.group(3))
    if year < 100:
        year += 2000
    if first > 12 and second <= 12:
        day, month = first, second
    elif second > 12 and first <= 12:
        month, day = first, second
    else:
        return None, Confidence.low
    return _safe_date(year, month, day), Confidence.high


def _parse_range(
    text: str,
    reference: datetime | None,
) -> tuple[str | None, str | None, str | None, DatePrecision, Confidence] | None:
    between = re.fullmatch(r"between\s+(.+?)\s+and\s+(.+)", text.strip(), re.IGNORECASE)
    if between:
        left = _parse_when(between.group(1), reference, None, None)
        right = _parse_when(between.group(2), reference, None, None)
        if left and right and left[0] and right[0]:
            return f"{left[0][:10]}/{right[0][:10]}", None, left[2], DatePrecision.range, Confidence.high
        return None, None, None, DatePrecision.range, Confidence.medium
    span = re.fullmatch(
        rf"({_MONTH})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\s*[-–]\s*(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(\d{{4}}))?",
        text.strip(),
        re.IGNORECASE,
    )
    if not span:
        return None
    month = month_number(span.group(1))
    if month is None:
        return None
    year = int(span.group(4)) if span.group(4) else None
    start = _with_year(month, int(span.group(2)), year, reference)
    end = _with_year(month, int(span.group(3)), year, reference)
    if start and end:
        return f"{start}/{end}", None, _offset(reference), DatePrecision.range, Confidence.high
    return None, None, None, DatePrecision.range, Confidence.medium


def _with_year(month: int, day: int, year: int | None, reference: datetime | None) -> str | None:
    if year is not None:
        return _safe_date(year, month, day)
    if reference is None:
        return None
    candidate = _safe_date(reference.year, month, day)
    if candidate is None:
        return None
    if datetime.fromisoformat(candidate).date() < reference.date() - timedelta(days=30):
        return _safe_date(reference.year + 1, month, day)
    return candidate


def _safe_date(year: int, month: int, day: int) -> str | None:
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return None


def _normalize_clock(value: str) -> str:
    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", value.strip(), re.IGNORECASE)
    if not match:
        return value.strip()
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridian = (match.group(3) or "").lower()
    if meridian == "pm" and hour < 12:
        hour += 12
    if meridian == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def _offset(reference: datetime | None) -> str | None:
    if reference is None or reference.tzinfo is None or reference.utcoffset() is None:
        return None
    total = int(reference.utcoffset().total_seconds())  # type: ignore[union-attr]
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    hours, rem = divmod(total, 3600)
    return f"{sign}{hours:02d}:{rem // 60:02d}"
