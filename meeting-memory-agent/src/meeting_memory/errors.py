"""User-facing errors. Messages stay free of transcript text and secrets."""


class MeetingMemoryError(Exception):
    """Base error for problems the CLI should print and exit on."""


class ConfigurationError(MeetingMemoryError):
    """Missing or invalid configuration."""


class InputError(MeetingMemoryError):
    """A recording or transcript could not be read."""


class UnsupportedInputError(MeetingMemoryError):
    """The file is not a meeting transcript or recording."""


class TranscriptionError(MeetingMemoryError):
    """Audio could not be turned into a transcript."""


class NotFoundError(MeetingMemoryError):
    """No indexed meeting matches the requested name or id."""


class CorruptIndexError(MeetingMemoryError):
    """The index exists but cannot be read safely."""
