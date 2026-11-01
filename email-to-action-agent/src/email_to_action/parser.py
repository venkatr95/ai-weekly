"""Parse plain-text email and .eml threads into chronological messages."""

from __future__ import annotations

import email
import re
from datetime import datetime
from email import policy
from email.utils import parsedate_to_datetime
from html import unescape

from email_to_action.preprocessor import greeting_name, prepare_body, signature_name
from email_to_action.schemas import EmailMessage, Participant
from email_to_action.textutil import normalize_whitespace

_MONTH_NUMBERS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
_HEADER_NAMES = {"from", "to", "cc", "bcc", "date", "sent", "subject", "reply-to"}
_MARKER = re.compile(
    r"(?im)^[ \t]*(?:(?:-{2,}|_{5,})\s*)?(?:original message|forwarded message)(?:\s*(?:-{2,}|_{5,}))?\s*$"
    r"|^[ \t]*On .+ wrote:\s*$"
)
_ON_WROTE_LINE = re.compile(r"(?im)^[ \t]*On (?P<rest>.+) wrote:\s*$")
_HEADER_LINE = re.compile(r"^([A-Za-z-]+):\s*(.*)$")
_MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)


def parse_text(text: str) -> tuple[list[EmailMessage], list[str]]:
    warnings: list[str] = []
    normalized = normalize_whitespace(text)
    if not normalized:
        return [], ["Email text is empty."]
    lifted = _lift_quoted_runs(normalized)
    chunks = _split_chronological(lifted)
    messages = [_chunk_to_message(chunk) for chunk in chunks if chunk.strip()]
    messages = [message for message in messages if message.body or message.sender_name or message.subject]
    messages, order_warnings = _order_messages(messages)
    warnings.extend(order_warnings)
    for index, message in enumerate(messages, start=1):
        message.message_id = f"message-{index}"
    if any(message.quoted_text for message in messages):
        warnings.append(
            "Quoted lines that were not a separate message were kept out of the action text."
        )
    return messages, warnings


def parse_eml(data: bytes) -> tuple[list[EmailMessage], list[str]]:
    message = email.message_from_bytes(data, policy=policy.default)
    body, warnings = _eml_body(message)
    synthesized = "\n".join(
        [
            f"From: {message.get('from', '')}",
            f"To: {message.get('to', '')}",
            f"Cc: {message.get('cc', '')}",
            f"Date: {message.get('date', '')}",
            f"Subject: {message.get('subject', '')}",
            "",
            body,
        ]
    )
    messages, more = parse_text(synthesized)
    return messages, warnings + more


def parse_message_datetime(value: str | None) -> datetime | None:
    if not value or not value.strip():
        return None
    raw = value.strip()
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError, OverflowError):
        parsed = None
    if parsed is not None:
        return parsed
    if re.match(r"^\d{4}-\d{2}-\d{2}", raw):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    cleaned = re.sub(
        r"^(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday),?\s+",
        "",
        raw,
        flags=re.IGNORECASE,
    )
    match = re.match(
        rf"^(?P<mon>{_MONTH})\.?\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(?P<year>\d{{4}}))"
        rf"(?:\s+(?P<time>\d{{1,2}}(?::\d{{2}})?\s*(?:am|pm)?))?\s*$",
        cleaned,
        re.IGNORECASE,
    )
    if not match:
        return None
    month = _MONTH_NUMBERS.get(match.group("mon").lower().rstrip("."))
    if month is None:
        return None
    hour, minute = 0, 0
    if match.group("time"):
        hour, minute = _clock_from_loose(match.group("time"))
    return datetime(int(match.group("year")), month, int(match.group("day")), hour, minute)


def _eml_body(message: email.message.EmailMessage) -> tuple[str, list[str]]:
    warnings: list[str] = []
    plain = message.get_body(preferencelist=("plain",))
    if plain is not None:
        content = plain.get_content()
        return content if isinstance(content, str) else str(content), warnings
    html = message.get_body(preferencelist=("html",))
    if html is not None:
        content = html.get_content()
        text = content if isinstance(content, str) else str(content)
        warnings.append("The .eml body was HTML and was converted to text.")
        return _html_to_text(text), warnings
    fallback = message.get_content()
    if isinstance(fallback, str):
        return fallback, warnings
    return "", ["The .eml file had no readable body."]


def _html_to_text(value: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return unescape(text)


def _lift_quoted_runs(text: str) -> str:
    lines = text.split("\n")
    output: list[str] = []
    index = 0
    while index < len(lines):
        if lines[index].lstrip().startswith(">"):
            block: list[str] = []
            while index < len(lines) and (
                lines[index].lstrip().startswith(">")
                or (
                    not lines[index].strip()
                    and index + 1 < len(lines)
                    and lines[index + 1].lstrip().startswith(">")
                )
            ):
                raw = lines[index]
                if raw.lstrip().startswith(">"):
                    raw = re.sub(r"^[ \t]*>[ \t]?", "", raw)
                block.append(raw)
                index += 1
            unquoted = "\n".join(block).strip()
            if re.search(r"(?im)^(?:from:\s+\S|on .+ wrote:)", unquoted):
                output.append("-----Original Message-----")
                output.append(unquoted)
            else:
                output.extend(f"> {line}" if line.strip() else "" for line in block)
            continue
        output.append(lines[index])
        index += 1
    return "\n".join(output)


def _split_chronological(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    match = _MARKER.search(stripped)
    if not match:
        return _split_header_messages(stripped)
    before = stripped[: match.start()].strip()
    marker_line = stripped[match.start() : match.end()].strip()
    after = stripped[match.end() :].strip()
    wrote = _parse_on_wrote(marker_line)
    if wrote:
        when, name = wrote
        after = "\n".join([f"From: {name}", f"Date: {when}", "", after])
    older = _split_chronological(after) if after else []
    newer = _split_chronological(before) if before else []
    return [*older, *newer]


def _split_header_messages(text: str) -> list[str]:
    lines = text.split("\n")
    starts = [index for index in range(len(lines)) if _is_header_start(lines, index)]
    if not starts:
        return [text]
    if starts[0] != 0 and "\n".join(lines[: starts[0]]).strip():
        starts = [0, *starts]
    chunks: list[str] = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        chunk = "\n".join(lines[start:end]).strip()
        if chunk:
            chunks.append(chunk)
    return chunks or [text]


def _is_header_start(lines: list[str], index: int) -> bool:
    if not re.match(r"^From:\s+\S", lines[index]):
        return False
    keys: set[str] = set()
    for offset, line in enumerate(lines[index : index + 8]):
        if offset and not line.strip():
            break
        match = _HEADER_LINE.match(line)
        if not match or match.group(1).lower() not in _HEADER_NAMES:
            if offset == 0:
                return False
            break
        keys.add(match.group(1).lower())
    return "from" in keys and bool(keys & {"subject", "date", "sent", "to", "cc"})


def _chunk_to_message(chunk: str) -> EmailMessage:
    headers, body = _split_headers(chunk.strip())
    first_line = body.split("\n", 1)[0] if body else ""
    wrote = _parse_on_wrote(first_line)
    if wrote and not headers:
        when, name = wrote
        headers = {"from": name, "date": when}
        body = "\n".join(body.split("\n")[1:])
    content, quoted, signature, greeting = prepare_body(body)
    sender = _parse_one(headers.get("from"))
    if sender.name is None and sender.email is None:
        recovered = signature_name(signature)
        if recovered:
            sender = Participant(name=recovered, email=None, role="sender")
    recipients = _parse_many(headers.get("to"), "recipient")
    copied = _parse_many(headers.get("cc"), "cc")
    addressee, ambiguous = _choose_addressee(recipients, greeting)
    date_raw = headers.get("date") or headers.get("sent")
    parsed = parse_message_datetime(date_raw)
    subject = headers.get("subject") or None
    return EmailMessage(
        message_id="message-0",
        sender_name=sender.name,
        sender_email=sender.email,
        to=recipients,
        cc=copied,
        subject=subject,
        date_raw=date_raw,
        date_iso=parsed.isoformat() if parsed else None,
        body=content,
        quoted_text=quoted,
        signature=signature,
        addressee_name=addressee,
        addressee_ambiguous=ambiguous,
    )


def _split_headers(text: str) -> tuple[dict[str, str], str]:
    lines = text.split("\n")
    index = 0
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines) or not _is_header_line(lines[index]):
        return {}, text.strip()
    headers: dict[str, str] = {}
    current: str | None = None
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            break
        if line[0] in " \t" and current:
            headers[current] = f"{headers[current]} {line.strip()}".strip()
            index += 1
            continue
        if not _is_header_line(line):
            break
        match = _HEADER_LINE.match(line)
        assert match is not None
        current = match.group(1).lower()
        headers[current] = match.group(2).strip()
        index += 1
    return headers, "\n".join(lines[index:]).strip()


def _is_header_line(line: str) -> bool:
    match = _HEADER_LINE.match(line)
    return bool(match and match.group(1).lower() in _HEADER_NAMES)


def _parse_one(value: str | None) -> Participant:
    people = _parse_many(value, "sender")
    if not people:
        return Participant(name=None, email=None, role="sender")
    person = people[0]
    person.role = "sender"
    return person


def _parse_many(value: str | None, role: str) -> list[Participant]:
    if not value or not value.strip():
        return []
    people: list[Participant] = []
    for part in _split_addresses(value):
        match = re.match(
            r"^(?:\"(?P<quoted>[^\"]+)\"|(?P<name>[^<]+?))?\s*<(?P<email>[^>]+)>\s*$",
            part,
        )
        if match:
            name = (match.group("quoted") or match.group("name") or "").strip() or None
            people.append(Participant(name=name, email=match.group("email").strip(), role=role))  # type: ignore[arg-type]
            continue
        if "@" in part:
            people.append(Participant(name=None, email=part.strip(), role=role))  # type: ignore[arg-type]
            continue
        people.append(Participant(name=part.strip(), email=None, role=role))  # type: ignore[arg-type]
    return people


def _split_addresses(value: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    in_quotes = False
    depth = 0
    for character in value:
        if character == '"':
            in_quotes = not in_quotes
        elif character == "<" and not in_quotes:
            depth += 1
        elif character == ">" and not in_quotes and depth:
            depth -= 1
        if character == "," and not in_quotes and depth == 0:
            piece = "".join(current).strip()
            if piece:
                parts.append(piece)
            current = []
            continue
        current.append(character)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def _choose_addressee(recipients: list[Participant], greeting: str | None) -> tuple[str | None, bool]:
    names = [person.name for person in recipients if person.name]
    if len(recipients) > 1:
        if greeting and any(_same_name(greeting, name) for name in names if name):
            return greeting, True
        if greeting and not names:
            return greeting, True
        return None, True
    if len(names) == 1:
        if greeting and not _same_name(greeting, names[0]):
            return None, True
        return names[0], False
    if greeting:
        return greeting, False
    if len(recipients) == 1 and recipients[0].email:
        return recipients[0].email, False
    return None, False


def _same_name(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    return left.strip().lower() == right.strip().lower()


def _order_messages(messages: list[EmailMessage]) -> tuple[list[EmailMessage], list[str]]:
    if len(messages) < 2:
        return messages, []
    if all(message.date_iso for message in messages):
        return sorted(messages, key=lambda message: message.date_iso or ""), []
    if any(message.date_iso for message in messages):
        return messages, ["Message order follows the text because a timestamp is missing on part of the thread."]
    return messages, []


def _parse_on_wrote(line: str) -> tuple[str, str] | None:
    match = _ON_WROTE_LINE.match(line.strip())
    if not match:
        return None
    rest = match.group("rest").strip().rstrip(",")
    name_match = re.search(r"([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+){0,2})$", rest)
    if not name_match:
        return None
    name = name_match.group(1).strip()
    when = rest[: name_match.start()].strip(" ,")
    if not name or not when:
        return None
    return when, name


def _clock_from_loose(value: str) -> tuple[int, int]:
    match = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", value.strip(), re.IGNORECASE)
    if not match:
        return 0, 0
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridian = (match.group(3) or "").lower()
    if meridian == "pm" and hour < 12:
        hour += 12
    if meridian == "am" and hour == 12:
        hour = 0
    return hour, minute
