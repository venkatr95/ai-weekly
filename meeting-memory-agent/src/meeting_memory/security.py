"""Limits for untrusted meeting files.

Transcript text is data. It is stored and quoted. It is never executed, and it
cannot change how questions are answered.
"""

from __future__ import annotations

from pathlib import Path

from meeting_memory.errors import InputError


def read_text_file(path: Path, limit: int) -> str:
    size = path.stat().st_size
    if size > limit:
        raise InputError(f"{path.name} exceeds the {limit} byte text limit.")
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InputError(f"{path.name} is not valid UTF-8.") from exc


def check_audio_size(path: Path, limit: int) -> None:
    size = path.stat().st_size
    if size > limit:
        raise InputError(f"{path.name} exceeds the {limit} byte audio limit.")
