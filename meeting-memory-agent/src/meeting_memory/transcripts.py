"""Parsers for speaker transcripts, WebVTT, SRT, JSON, and written notes."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from meeting_memory.dates import parse_meeting_date
from meeting_memory.errors import InputError, UnsupportedInputError
from meeting_memory.timestamps import coerce_time, parse_ms, format_ms

_TS = r"\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d+)?"
_HEADER = re.compile(
    r"^(?:#{1,6}\s*)?(?P<key>meeting|title|date|held|time|participants|attendees|language)\s*:\s*(?P<value>.+)$",
    re.IGNORECASE,
)
_SPEAKER = r"[A-Za-z][A-Za-z0-9 .'_-]{0,40}"
_SPOKEN = re.compile(
    rf"^(?:\[(?P<ts>{_TS})\]\s*)?(?:\*\*)?(?P<speaker>{_SPEAKER})(?:\*\*)?:\s*(?P<text>\S.*)$"
)
_CUE = re.compile(rf"^(?P<start>{_TS})\s+-->\s+(?P<end>{_TS})(?:\s+.*)?$")
_VOICE = re.compile(r"^<v(?:\.\w+)?\s+([^>]+)>(.*?)(?:</v>)?$", re.IGNORECASE)
_FILENAME_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:[-_]|$)")
_FILENAME_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}[-_](.+)$")


@dataclass
class ParsedUtterance:
    speaker: str | None
    start: str | None
    end: str | None
    text: str
    line_start: int
    confidence: float | None = None


@dataclass
class ParsedTranscript:
    name: str | None = None
    held_on: str | None = None
    held_at: str | None = None
    participants: list[str] = field(default_factory=list)
    utterances: list[ParsedUtterance] = field(default_factory=list)
    language: str | None = None
    confidence: float | None = None


def parse_transcript(path: Path, text: str | None = None) -> ParsedTranscript:
    raw = path.read_text(encoding="utf-8-sig") if text is None else text
    suffix = path.suffix.lower()
    if suffix == ".json":
        parsed = _parse_json(raw, path.name)
    elif suffix in {".vtt", ".srt"} or _looks_like_cues(raw):
        parsed = _parse_cues(raw)
    else:
        parsed = _parse_lines(raw)
    if parsed.name is None:
        parsed.name = _name_from_filename(path)
    if parsed.held_on is None:
        parsed.held_on = _date_from_filename(path)
    _add_speakers(parsed)
    return parsed


def _parse_lines(raw: str) -> ParsedTranscript:
    parsed = ParsedTranscript()
    current: ParsedUtterance | None = None
    for line_number, raw_line in enumerate(raw.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line == "---":
            current = None
            continue
        header = _HEADER.match(line)
        if header:
            _apply_header(parsed, header.group("key"), header.group("value"))
            current = None
            continue
        if line.startswith("#"):
            current = None
            continue
        spoken = _SPOKEN.match(line)
        if spoken:
            start = None
            if spoken.group("ts"):
                start = format_ms(parse_ms(spoken.group("ts")))
            current = ParsedUtterance(
                speaker=spoken.group("speaker").strip(),
                start=start,
                end=None,
                text=spoken.group("text").strip(),
                line_start=line_number,
            )
            parsed.utterances.append(current)
            continue
        if current is not None:
            current.text = f"{current.text} {line}".strip()
    return parsed


def _parse_cues(raw: str) -> ParsedTranscript:
    parsed = ParsedTranscript()
    lines = raw.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        header = _HEADER.match(line)
        if header:
            _apply_header(parsed, header.group("key"), header.group("value"))
            index += 1
            continue
        if not line or line.upper().startswith("WEBVTT") or line.upper().startswith("NOTE") or line.isdigit():
            if line.upper().startswith("NOTE"):
                index += 1
                while index < len(lines) and lines[index].strip():
                    index += 1
            index += 1
            continue
        cue = _CUE.match(line)
        if not cue:
            index += 1
            continue
        start = format_ms(parse_ms(cue.group("start")))
        end = format_ms(parse_ms(cue.group("end")))
        text_lines: list[str] = []
        line_start = index + 1
        index += 1
        while index < len(lines) and lines[index].strip():
            text_lines.append(lines[index].strip())
            index += 1
        speaker, text = _cue_text(text_lines)
        if text:
            parsed.utterances.append(
                ParsedUtterance(
                    speaker=speaker,
                    start=start,
                    end=end,
                    text=text,
                    line_start=line_start,
                )
            )
    return parsed


def _cue_text(lines: list[str]) -> tuple[str | None, str]:
    speaker: str | None = None
    pieces: list[str] = []
    for line in lines:
        voice = _VOICE.match(line)
        if voice:
            speaker = voice.group(1).strip()
            pieces.append(voice.group(2).strip())
            continue
        spoken = _SPOKEN.match(line)
        if spoken and not spoken.group("ts"):
            speaker = spoken.group("speaker").strip()
            pieces.append(spoken.group("text").strip())
            continue
        pieces.append(line)
    text = " ".join(piece for piece in pieces if piece).strip()
    return speaker, text


def _parse_json(raw: str, name: str) -> ParsedTranscript:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise UnsupportedInputError(f"{name} is not a meeting transcript.") from exc
    if isinstance(payload, list):
        utterances = payload
        meta: dict[str, object] = {}
    elif isinstance(payload, dict):
        meta = payload
        utterances = payload.get("utterances") or payload.get("segments") or payload.get("cues")
    else:
        raise UnsupportedInputError(f"{name} is not a meeting transcript.")
    if not isinstance(utterances, list):
        raise UnsupportedInputError(f"{name} is not a meeting transcript.")
    parsed = ParsedTranscript()
    title = meta.get("name") or meta.get("meeting") or meta.get("title")
    if isinstance(title, str) and title.strip():
        parsed.name = title.strip()
    held = meta.get("date") or meta.get("held_on") or meta.get("held")
    if isinstance(held, str):
        parsed.held_on = parse_meeting_date(held)
    people = meta.get("participants") or meta.get("attendees") or []
    if isinstance(people, str):
        parsed.participants = _split_people(people)
    elif isinstance(people, list):
        parsed.participants = [str(person).strip() for person in people if str(person).strip()]
    for index, item in enumerate(utterances, start=1):
        if not isinstance(item, dict) or "text" not in item:
            raise InputError(f"{name} has an utterance without text.")
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        speaker = item.get("speaker") or item.get("voice")
        start, _start_ms = coerce_time(item.get("start") if "start" in item else item.get("start_time"))
        end, _end_ms = coerce_time(item.get("end") if "end" in item else item.get("end_time"))
        confidence = item.get("confidence")
        parsed.utterances.append(
            ParsedUtterance(
                speaker=str(speaker).strip() if speaker else None,
                start=start,
                end=end,
                text=text,
                line_start=index,
                confidence=float(confidence) if isinstance(confidence, (int, float)) else None,
            )
        )
    language = meta.get("language") if isinstance(meta, dict) else None
    if isinstance(language, str) and language.strip():
        parsed.language = language.strip()
    return parsed


def _apply_header(parsed: ParsedTranscript, key: str, value: str) -> None:
    normalized = key.lower()
    if normalized in {"meeting", "title"}:
        parsed.name = value.strip()
    elif normalized in {"date", "held"}:
        parsed.held_on = parse_meeting_date(value)
    elif normalized in {"participants", "attendees"}:
        parsed.participants = _split_people(value)
    elif normalized == "language":
        parsed.language = value.strip() or None
    elif normalized == "time":
        parsed.held_at = value.strip() or None


def _split_people(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _add_speakers(parsed: ParsedTranscript) -> None:
    seen = {name.casefold() for name in parsed.participants}
    for utterance in parsed.utterances:
        if utterance.speaker and utterance.speaker.casefold() not in seen:
            parsed.participants.append(utterance.speaker)
            seen.add(utterance.speaker.casefold())


def _looks_like_cues(raw: str) -> bool:
    return any(_CUE.match(line.strip()) for line in raw.splitlines())


def _name_from_filename(path: Path) -> str:
    match = _FILENAME_NAME.match(path.stem)
    stem = match.group(1) if match else path.stem
    name = stem.replace("_", " ").replace("-", " ").strip()
    return name or path.name


def _date_from_filename(path: Path) -> str | None:
    match = _FILENAME_DATE.match(path.stem)
    if not match:
        return None
    return parse_meeting_date(match.group(1))
