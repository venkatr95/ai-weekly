"""Turn meetings into an evidence-backed record of commitments and decisions."""

from meeting_memory.pipeline import MeetingMemory
from meeting_memory.schemas import Answer, MeetingSummary

__all__ = ["Answer", "MeetingMemory", "MeetingSummary"]
__version__ = "1.0.0"
