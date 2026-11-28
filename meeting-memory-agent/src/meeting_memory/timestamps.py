"""Timestamp parsing for transcripts and whisper segments."""

from __future__ import annotations

from meeting_memory.errors import InputError


def parse_ms(value: str) -> int:
    text = value.strip().replace(",", ".")
    parts = text.split(":")
    if len(parts) == 2:
        hours = "0"
        minutes, seconds = parts
    elif len(parts) == 3:
        hours, minutes, seconds = parts
    else:
        raise InputError(f"Unrecognized timestamp {value!r}.")
    sec, separator, frac = seconds.partition(".")
    try:
        hour_n = int(hours)
        minute_n = int(minutes)
        second_n = int(sec)
    except ValueError as exc:
        raise InputError(f"Unrecognized timestamp {value!r}.") from exc
    if hour_n < 0 or not 0 <= minute_n < 60 or not 0 <= second_n < 60:
        raise InputError(f"Unrecognized timestamp {value!r}.")
    millis = 0
    if separator:
        if not frac.isdigit():
            raise InputError(f"Unrecognized timestamp {value!r}.")
        millis = int((frac + "000")[:3])
    return ((hour_n * 60 + minute_n) * 60 + second_n) * 1000 + millis


def format_ms(milliseconds: int) -> str:
    total = max(0, int(milliseconds))
    hours, remainder = divmod(total, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    base = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    if millis:
        return f"{base}.{millis:03d}"
    return base


def to_seconds(value: str | None) -> float | None:
    """Convert a stored clock timestamp to seconds. Missing times stay missing."""

    if not value:
        return None
    return parse_ms(value) / 1000.0


def coerce_time(value: object) -> tuple[str | None, int | None]:
    if value is None or value == "":
        return None, None
    if isinstance(value, bool):
        raise InputError(f"Unrecognized timestamp {value!r}.")
    if isinstance(value, (int, float)):
        milliseconds = int(round(float(value) * 1000))
        if milliseconds < 0:
            raise InputError(f"Unrecognized timestamp {value!r}.")
        return format_ms(milliseconds), milliseconds
    text = str(value).strip()
    if not text:
        return None, None
    milliseconds = parse_ms(text)
    return format_ms(milliseconds), milliseconds
