"""Speaker labels from diarization stay anonymous.

A diarizer may separate voices. It must not assign a person's name. Manual
mapping is the only way a label such as SPEAKER_00 becomes a participant.
This module does not analyze audio and does not perform biometric recognition.
"""

from __future__ import annotations

import re

_ANONYMOUS = re.compile(r"^SPEAKER_\d+$", re.IGNORECASE)


def anonymous_label(index: int) -> str:
    return f"SPEAKER_{index:02d}"


def coerce_diarization_label(label: str | None, index: int) -> str | None:
    """Keep SPEAKER_NN labels. Replace any other diarizer label with one.

    index is 1-based so the first unnamed voice is SPEAKER_01 when the caller
    passes the segment number. A stored SPEAKER_00 value is preserved.
    """

    if label is None:
        return None
    text = str(label).strip()
    if not text:
        return None
    if _ANONYMOUS.fullmatch(text):
        return text.upper()
    return anonymous_label(index)
