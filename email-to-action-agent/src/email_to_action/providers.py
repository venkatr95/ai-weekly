"""Local extraction provider. Email text is not sent to a model."""

from __future__ import annotations

from datetime import datetime

from email_to_action.errors import EmailActionError
from email_to_action.extractor import Extraction, extract
from email_to_action.schemas import EmailMessage


class HeuristicProvider:
    """Deterministic extractor. The same email produces the same actions."""

    name = "heuristic"

    def extract(self, messages: list[EmailMessage], received_at: datetime | None = None) -> Extraction:
        return extract(messages, received_at=received_at)


def get_provider(name: str) -> HeuristicProvider:
    if name != "heuristic":
        raise EmailActionError(
            "Only the local heuristic provider is available. Email text is not sent to a model."
        )
    return HeuristicProvider()
