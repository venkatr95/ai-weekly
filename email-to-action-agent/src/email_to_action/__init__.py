"""Convert an email thread into an execution-ready action list."""

from email_to_action.pipeline import analyze
from email_to_action.schemas import ActionList, PublicReport

__all__ = ["ActionList", "PublicReport", "analyze"]
__version__ = "1.1.0"
