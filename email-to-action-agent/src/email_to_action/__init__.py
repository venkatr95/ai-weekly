"""Convert an email thread into an execution-ready action list."""

from email_to_action.pipeline import analyze
from email_to_action.schemas import ActionList

__all__ = ["ActionList", "analyze"]
__version__ = "1.0.0"
