"""Apply a user-supplied map from anonymous labels to participant names.

The map is explicit. Nothing in this module guesses a name from a voice.
"""

from __future__ import annotations

from meeting_memory.schemas import Meeting


def apply_speaker_map(meeting: Meeting) -> None:
    mapping = {label: name.strip() for label, name in meeting.speaker_map.items() if name.strip()}
    if not mapping:
        return
    participants: list[str] = []
    seen: set[str] = set()

    def add(name: str | None) -> None:
        if not name:
            return
        key = name.casefold()
        if key in seen:
            return
        seen.add(key)
        participants.append(name)

    for utterance in meeting.utterances:
        label = utterance.source_speaker or utterance.speaker
        if label in mapping:
            utterance.speaker = mapping[label]
        add(utterance.speaker)
    for name in meeting.participants:
        mapped = mapping.get(name, name)
        add(mapped)
    meeting.participants = participants
