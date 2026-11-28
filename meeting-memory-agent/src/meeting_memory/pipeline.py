"""Ingest meetings and answer questions from the local index."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from pydantic import ValidationError

from meeting_memory.answering import answer_question, compare_topic
from meeting_memory.audio_loader import inspect_audio
from meeting_memory.config import Settings
from meeting_memory.errors import (
    CorruptIndexError,
    InputError,
    NotFoundError,
    TranscriptionError,
    UnsupportedInputError,
)
from meeting_memory.evidence_validator import validate_answer
from meeting_memory.extraction import extract_items
from meeting_memory.linking import link_items, meeting_sort_key
from meeting_memory.rendering import build_summary
from meeting_memory.retrieval import hybrid_search
from meeting_memory.schemas import Corpus, IngestReport, Meeting, MeetingSummary, MemoryItem, Utterance
from meeting_memory.security import read_text_file
from meeting_memory.speaker_mapper import apply_speaker_map
from meeting_memory.timestamps import to_seconds
from meeting_memory.transcription import (
    AUDIO_SUFFIXES,
    TEXT_SUFFIXES,
    find_sidecar,
    transcribe_whisper,
)
from meeting_memory.transcripts import (
    _date_from_filename,
    _name_from_filename,
    parse_transcript,
)


@dataclass
class _Input:
    source: Path
    transcript: Path | None
    origin: str


class MeetingMemory:
    """Local memory of meeting decisions, commitments, and open questions."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()

    @property
    def index_path(self) -> Path:
        return self.settings.index_dir / "corpus.json"

    def ingest(self, path: Path, rebuild: bool = False) -> IngestReport:
        path = Path(path)
        if not path.exists():
            raise InputError(f"{path} does not exist.")
        if rebuild and self.index_path.exists():
            self.index_path.unlink()
        corpus = self._load()
        inputs, skipped, needs = self._discover(path)
        added: list[Meeting] = []
        failed: list[str] = []
        warnings: list[str] = []
        previous = {meeting.source_path: meeting for meeting in corpus.meetings}
        for item in inputs:
            try:
                meeting = self._read_meeting(item)
            except UnsupportedInputError as exc:
                skipped.append(str(exc))
                continue
            except (InputError, TranscriptionError) as exc:
                failed.append(str(exc))
                continue
            if not meeting.utterances:
                warnings.append(f"{item.source.name}: no utterances")
                continue
            prior = previous.get(meeting.source_path)
            if prior is not None and prior.speaker_map:
                meeting.speaker_map = dict(prior.speaker_map)
                meeting.speaker_map_confidence = dict(prior.speaker_map_confidence)
                apply_speaker_map(meeting)
            added.append(meeting)
        added, expired = self._apply_retention(added)
        warnings.extend(expired)
        replaced = {meeting.source_path for meeting in added}
        kept = [meeting for meeting in corpus.meetings if meeting.source_path not in replaced]
        kept, expired_kept = self._apply_retention(kept)
        warnings.extend(expired_kept)
        meetings = kept + added
        items = link_items(meetings, extract_items(meetings))
        self._save(Corpus(meetings=meetings, items=items))
        return IngestReport(
            meetings_added=len(added),
            meetings_total=len(meetings),
            files_skipped=skipped,
            files_needs_transcription=needs,
            files_failed=failed,
            warnings=warnings,
            index_dir=str(self.settings.index_dir),
        )

    def ask(self, question: str):
        corpus = self._load()
        answer = answer_question(corpus.meetings, corpus.items, question)
        return validate_answer(answer, corpus.meetings)

    def search(self, query: str, *, kind: str | None = None, owner: str | None = None, status: str | None = None):
        corpus = self._load()
        return hybrid_search(corpus.items, query, kind=kind, owner=owner, status=status)

    def compare(self, topic: str):
        corpus = self._load()
        return compare_topic(corpus.meetings, corpus.items, topic)

    def meetings(self) -> list[Meeting]:
        return sorted(self._load().meetings, key=meeting_sort_key)

    def items(self, kind: str | None = None, status: str | None = None) -> list[MemoryItem]:
        found = self._load().items
        if kind:
            found = [item for item in found if item.kind == kind]
        if status:
            found = [item for item in found if item.status == status]
        return found

    def delete(self, key: str) -> str:
        meeting = self.get_meeting(key)
        corpus = self._load()
        meetings = [item for item in corpus.meetings if item.meeting_id != meeting.meeting_id]
        items = link_items(meetings, extract_items(meetings))
        self._save(Corpus(meetings=meetings, items=items))
        return meeting.name

    def clear(self) -> None:
        self._save(Corpus())

    def map_speakers(self, key: str, label: str, name: str, confidence: float = 1.0) -> Meeting:
        cleaned_label = label.strip()
        cleaned_name = name.strip()
        if not cleaned_label or not cleaned_name:
            raise InputError("A speaker map needs both a label and a name.")
        if not 0.0 <= confidence <= 1.0:
            raise InputError("Speaker-map confidence must be between 0 and 1.")
        corpus = self._load()
        meeting = self._meeting_from(corpus.meetings, key)
        meeting.speaker_map[cleaned_label] = cleaned_name
        meeting.speaker_map_confidence[cleaned_label] = confidence
        apply_speaker_map(meeting)
        items = link_items(corpus.meetings, extract_items(corpus.meetings))
        self._save(Corpus(meetings=corpus.meetings, items=items))
        return meeting

    def get_meeting(self, key: str) -> Meeting:
        return self._meeting_from(self.meetings(), key)

    def _meeting_from(self, meetings: list[Meeting], key: str) -> Meeting:
        label = re.fullmatch(r"M(\d{3})", key.strip(), re.IGNORECASE)
        if label:
            number = int(label.group(1))
            ordered = sorted(meetings, key=meeting_sort_key)
            if 1 <= number <= len(ordered):
                return ordered[number - 1]
        for meeting in meetings:
            if meeting.meeting_id == key or meeting.name.casefold() == key.casefold():
                return meeting
        matches = [meeting for meeting in meetings if key.casefold() in meeting.name.casefold()]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise NotFoundError(f"No meeting matches {key!r}.")
        names = ", ".join(meeting.name for meeting in matches)
        raise NotFoundError(f"Meeting {key!r} matches more than one record: {names}.")

    def summary(self, key: str) -> MeetingSummary:
        meeting = self.get_meeting(key)
        return build_summary(meeting, self._load().items)

    def _discover(self, path: Path) -> tuple[list[_Input], list[str], list[str]]:
        files = self._files(path)
        audio = [file for file in files if file.suffix.lower() in AUDIO_SUFFIXES]
        text = [file for file in files if file.suffix.lower() in TEXT_SUFFIXES]
        skipped = [
            f"{file.name}: unsupported file"
            for file in files
            if file.suffix.lower() not in AUDIO_SUFFIXES | TEXT_SUFFIXES
        ]
        used: set[Path] = set()
        inputs: list[_Input] = []
        needs: list[str] = []
        for audio_path in audio:
            sidecar = find_sidecar(audio_path)
            if sidecar is not None:
                used.add(sidecar.resolve())
                inputs.append(_Input(audio_path, sidecar, "sidecar"))
                continue
            if self.settings.transcriber == "whisper":
                inputs.append(_Input(audio_path, None, "audio"))
            else:
                needs.append(
                    f"{audio_path.name}: recording needs a sidecar transcript "
                    "or MEETING_TRANSCRIBER=whisper"
                )
        for text_path in text:
            if text_path.resolve() in used:
                continue
            inputs.append(_Input(text_path, text_path, "transcript"))
        return inputs, skipped, needs

    def _files(self, path: Path) -> list[Path]:
        if path.is_file():
            return [path]
        if not path.is_dir():
            raise InputError(f"{path} does not exist.")
        found: list[Path] = []
        for candidate in path.rglob("*"):
            if not candidate.is_file():
                continue
            relative = candidate.relative_to(path)
            if any(part.startswith(".") for part in relative.parts):
                continue
            found.append(candidate)
        return sorted(found)

    def _read_meeting(self, item: _Input) -> Meeting:
        if item.origin == "audio":
            inspect_audio(item.source, self.settings.max_audio_bytes)
            parsed = transcribe_whisper(item.source, self.settings.whisper_model)
            parsed.name = parsed.name or _name_from_filename(item.source)
            parsed.held_on = parsed.held_on or _date_from_filename(item.source)
            return self._meeting(item.source, item.source, "whisper", parsed)
        transcript = item.transcript or item.source
        if item.origin == "sidecar":
            inspect_audio(item.source, self.settings.max_audio_bytes)
        raw = read_text_file(transcript, self.settings.max_text_bytes)
        parsed = parse_transcript(transcript, raw)
        return self._meeting(item.source, transcript, item.origin, parsed)

    def _meeting(self, source: Path, transcript: Path, origin: str, parsed) -> Meeting:
        meeting_id = _stable_id("mtg", str(source.resolve()))
        utterances: list[Utterance] = []
        for index, item in enumerate(parsed.utterances):
            text = item.text.strip()
            if not text:
                continue
            utterances.append(
                Utterance(
                    utterance_id=_stable_id("utt", meeting_id, str(index), text),
                    index=index,
                    speaker=item.speaker,
                    source_speaker=item.speaker,
                    start=item.start,
                    end=item.end,
                    start_seconds=to_seconds(item.start),
                    end_seconds=to_seconds(item.end),
                    text=text,
                    line_start=item.line_start,
                    confidence=item.confidence,
                )
            )
        recording = source.name if origin in {"sidecar", "whisper"} else None
        return Meeting(
            meeting_id=meeting_id,
            name=parsed.name or source.stem,
            held_on=parsed.held_on,
            held_at=parsed.held_at,
            participants=list(parsed.participants),
            source_path=str(source.resolve()),
            transcript_path=str(transcript.resolve()),
            recording_filename=recording,
            origin=origin,  # type: ignore[arg-type]
            language=parsed.language,
            processing_status="ready",
            utterances=utterances,
        )

    def _apply_retention(self, meetings: list[Meeting]) -> tuple[list[Meeting], list[str]]:
        if self.settings.retention_days is None:
            return meetings, []
        cutoff = date.today() - timedelta(days=self.settings.retention_days)
        kept: list[Meeting] = []
        warnings: list[str] = []
        for meeting in meetings:
            if meeting.held_on and date.fromisoformat(meeting.held_on) < cutoff:
                warnings.append(f"{meeting.name}: removed by the retention policy")
                continue
            kept.append(meeting)
        return kept, warnings

    def _load(self) -> Corpus:
        if not self.index_path.exists():
            return Corpus()
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
            return Corpus.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise CorruptIndexError(f"The index at {self.index_path} could not be read.") from exc

    def _save(self, corpus: Corpus) -> None:
        self.settings.index_dir.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(corpus.model_dump_json(indent=2), encoding="utf-8")


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"
