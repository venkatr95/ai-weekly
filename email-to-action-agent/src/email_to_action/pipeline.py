"""Public entry point: email text or a file in, a validated action list out."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from email_to_action.config import Settings
from email_to_action.errors import EmailActionError
from email_to_action.parser import parse_eml, parse_text
from email_to_action.providers import get_provider
from email_to_action.reply import build_reply
from email_to_action.schemas import ActionList, EmailMessage, Participant, Task
from email_to_action.security import check_size

logger = logging.getLogger("email_to_action")
_TEAM = re.compile(r"\b([A-Za-z]+(?:\s+[A-Za-z]+)?\s+team)\b", re.IGNORECASE)


def analyze(
    source: str | Path,
    settings: Settings | None = None,
    *,
    received_at: str | None = None,
    tone: str = "professional",
    include_reply: bool = True,
) -> ActionList:
    """Analyze an email. Mailbox integrations are not called from this pipeline."""
    settings = settings or Settings()
    if tone not in {"professional", "friendly", "concise", "formal"}:
        raise EmailActionError("tone must be professional, friendly, concise, or formal.")
    reference = _parse_received_at(received_at) if received_at is not None else None
    payload = _load(source, settings)
    if isinstance(payload, bytes):
        check_size(payload.decode("utf-8", errors="replace"), settings.max_chars)
        messages, warnings = parse_eml(payload)
    else:
        check_size(payload, settings.max_chars)
        if not payload.strip():
            raise EmailActionError("Email text is empty.")
        messages, warnings = parse_text(payload)
    if not messages:
        raise EmailActionError("No email message was found in the input.")
    extracted = get_provider(settings.provider).extract(messages, received_at=reference)
    warnings.extend(extracted.warnings)
    for message in messages:
        warnings.extend(message.warnings)
    if reference is not None and any(not message.date_iso for message in messages):
        warnings.append(
            "Messages without a Date header use the supplied received-at timestamp for relative dates. "
            "That timestamp is not text from the email."
        )
    reply = None
    if include_reply:
        reply = build_reply(messages, extracted.tasks, extracted.questions, extracted.commitments, tone=tone)
    action = ActionList(
        subject=next((message.subject for message in messages if message.subject), None),
        participants=_participants(messages, extracted.tasks),
        messages=messages,
        tasks=extracted.tasks,
        questions=extracted.questions,
        commitments=extracted.commitments,
        draft_reply=reply,
        warnings=_unique(warnings),
        reference_timestamp=reference.isoformat() if reference else None,
    )
    validated = ActionList.model_validate(action.model_dump())
    logger.info(
        "messages=%s tasks=%s questions=%s commitments=%s",
        len(validated.messages),
        len(validated.tasks),
        len(validated.questions),
        len(validated.commitments),
    )
    return validated


def _parse_received_at(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise EmailActionError(
            "received-at must be an ISO-8601 timestamp such as 2026-11-01T09:00:00+01:00."
        ) from exc


def _load(source: str | Path, settings: Settings) -> str | bytes:
    if isinstance(source, Path) or _looks_like_path(source):
        path = Path(source)
        if isinstance(source, Path) or path.is_file():
            if not path.is_file():
                raise EmailActionError(f"File not found: {path}")
            if path.stat().st_size > settings.max_chars * 4:
                raise EmailActionError(f"File is larger than the {settings.max_chars} character limit.")
            if path.suffix.lower() == ".eml":
                return path.read_bytes()
            return path.read_text(encoding="utf-8")
    if not isinstance(source, str):
        raise EmailActionError("Email input must be text or a file path.")
    return source


def _looks_like_path(source: str | Path) -> bool:
    return isinstance(source, str) and "\n" not in source and "\r" not in source and len(source) < 4096


def _participants(messages: list[EmailMessage], tasks: list[Task]) -> list[Participant]:
    found: list[Participant] = []

    def add(name: str | None, email: str | None, role: str) -> None:
        if not name and not email:
            return
        for existing in found:
            same_email = bool(email and existing.email and existing.email.lower() == email.lower())
            same_name = bool(name and existing.name and existing.name.lower() == name.lower() and existing.role == role)
            if same_email or same_name:
                return
        found.append(Participant(name=name, email=email, role=role))  # type: ignore[arg-type]

    for message in messages:
        add(message.sender_name, message.sender_email, "sender")
        for person in message.to:
            add(person.name, person.email, "recipient")
        for person in message.cc:
            add(person.name, person.email, "cc")
        if message.addressee_name:
            add(message.addressee_name, None, "recipient")
    for task in tasks:
        if task.owner.name and task.owner.role in {"named", "team"}:
            add(task.owner.name, task.owner.email, "mentioned")
        for match in _TEAM.finditer(task.supporting_text):
            name = re.sub(r"^the\s+", "", match.group(1), flags=re.IGNORECASE)
            add(name, None, "mentioned")
    return found


def _unique(warnings: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for warning in warnings:
        if warning in seen:
            continue
        seen.add(warning)
        ordered.append(warning)
    return ordered
