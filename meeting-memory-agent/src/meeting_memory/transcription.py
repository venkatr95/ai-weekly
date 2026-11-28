"""Audio transcription.

The default ingester does not invent speech. It reads a sidecar transcript
(.vtt, .srt, .json, .txt, or .md) with the same file name as the recording.
MEETING_TRANSCRIBER=whisper uses a local faster-whisper model. That path does
not identify speakers. Speaker names still have to come from a transcript.
"""

from __future__ import annotations

from pathlib import Path

from meeting_memory.diarization import coerce_diarization_label
from meeting_memory.errors import TranscriptionError
from meeting_memory.timestamps import format_ms
from meeting_memory.transcripts import ParsedTranscript, ParsedUtterance

SIDECAR_SUFFIXES = (".vtt", ".srt", ".json", ".txt", ".md", ".markdown")
AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm", ".mp4"}
TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".vtt", ".srt", ".json"}


def find_sidecar(audio_path: Path) -> Path | None:
    for suffix in SIDECAR_SUFFIXES:
        candidate = audio_path.with_suffix(suffix)
        if candidate.is_file() and candidate.resolve() != audio_path.resolve():
            return candidate
    return None


def transcribe_whisper(path: Path, model_name: str) -> ParsedTranscript:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise TranscriptionError(
            "Audio transcription requires the optional faster-whisper package. "
            "Install it, or place a .vtt, .srt, .json, .txt, or .md transcript next to the recording."
        ) from exc
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(path))
    language = getattr(info, "language", None) if info is not None else None
    language_probability = getattr(info, "language_probability", None) if info is not None else None
    utterances: list[ParsedUtterance] = []
    for index, segment in enumerate(segments, start=1):
        text = str(getattr(segment, "text", "") or "").strip()
        if not text:
            continue
        start_s = float(getattr(segment, "start", 0.0) or 0.0)
        end_value = getattr(segment, "end", None)
        end_s = float(end_value) if end_value is not None else None
        raw_speaker = getattr(segment, "speaker", None)
        speaker = coerce_diarization_label(str(raw_speaker), index) if raw_speaker else None
        logprob = getattr(segment, "avg_logprob", None)
        utterances.append(
            ParsedUtterance(
                speaker=speaker,
                start=format_ms(int(round(start_s * 1000))),
                end=format_ms(int(round(end_s * 1000))) if end_s is not None else None,
                text=text,
                line_start=index,
                confidence=float(logprob) if isinstance(logprob, (int, float)) else None,
            )
        )
    if not utterances:
        raise TranscriptionError(f"{path.name} produced no transcript text.")
    return ParsedTranscript(
        utterances=utterances,
        language=language if isinstance(language, str) else None,
        confidence=float(language_probability) if isinstance(language_probability, (int, float)) else None,
    )
