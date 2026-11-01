"""Small text helpers shared by the parser and the extractor."""

from __future__ import annotations

import re

STOPWORDS = {
    "a",
    "an",
    "the",
    "to",
    "of",
    "and",
    "or",
    "for",
    "by",
    "on",
    "in",
    "with",
    "please",
    "you",
    "your",
    "this",
    "that",
    "these",
    "those",
    "once",
    "after",
    "before",
    "when",
    "is",
    "are",
    "be",
    "been",
    "being",
    "complete",
    "completed",
    "items",
    "item",
    "tasks",
    "task",
    "from",
    "into",
    "about",
    "than",
    "then",
    "them",
    "they",
    "their",
    "just",
    "also",
    "will",
    "would",
    "could",
    "should",
    "have",
    "has",
    "had",
    "not",
    "but",
    "our",
    "out",
    "all",
    "any",
    "can",
    "day",
    "days",
}


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ").replace("\u200b", "")
    lines = [line.rstrip() for line in text.split("\n")]
    collapsed = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return collapsed.strip()


def tokens(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]+", text.lower()) if len(word) > 2 and word not in STOPWORDS}


def clean_description(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip(" \t-;:,")
    if not text:
        return text
    text = text[0].upper() + text[1:]
    if text[-1] not in ".?!":
        text += "."
    return text


def first_name(name: str | None) -> str | None:
    if not name:
        return None
    parts = name.replace(",", " ").split()
    if not parts:
        return None
    return parts[0]
