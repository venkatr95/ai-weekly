"""Public entry point: email text or a file in, a validated action list out."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from email_to_action.config import Settings
from email_to_action.errors import EmailActionError
from email_to_action.extractor import extract
from email_to_action.parser import parse_eml, parse_text
from email_to_action.reply import build_reply
from email_to_action.schemas import ActionList, EmailMessage, Participant, Task
from email_to_action.security import check_size

logger = logging.getLogger("email_to_action")
_TEAM = re.compile(r"\b([A-Za-z]+(?:\s+[A-Za-z]+)?\s+team)\b", re.IGNORECASE)


def analyze(source: str | Path, settings: Settings | None = None) -> ActionList:
    settings = settings or Settings()
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
    extracted = extract(messages)
    warnings.extend(extracted.warnings)
    for message in messages:
        warnings.extend(message.warnings)
    reply = build_reply(messages, extracted.tasks, extracted.questions, extracted.commitments)
    action = ActionList(
        subject=next((message.subject for message in messages if message.subject), None),
        participants=_participants(messages, extracted.tasks),
        messages=messages,
        tasks=extracted.tasks,
        questions=extracted.questions,
        commitments=extracted.commitments,
        draft_reply=reply,
        warnings=_unique(warnings),
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
