"""Check a recording before transcription. Audio bytes are never executed."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from meeting_memory.errors import UnsupportedInputError
from meeting_memory.security import check_audio_size
from meeting_memory.transcription import AUDIO_SUFFIXES


@dataclass(frozen=True)
class AudioSource:
    path: Path
    suffix: str
    size_bytes: int


def inspect_audio(path: Path, max_bytes: int) -> AudioSource:
    suffix = path.suffix.lower()
    if suffix not in AUDIO_SUFFIXES:
        raise UnsupportedInputError(f"{path.name}: unsupported audio format.")
    check_audio_size(path, max_bytes)
    return AudioSource(path=path, suffix=suffix, size_bytes=path.stat().st_size)
