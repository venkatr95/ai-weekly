"""Split answer and source text into sentences and paragraphs.

This is a small rule-based segmenter. It avoids a spaCy model download so the
audit runs offline. Abbreviations and decimals do not start a new sentence.
"""

from __future__ import annotations

import re

_ABBREVIATIONS = frozenset(
    {
        "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "vs", "etc", "eg", "ie", "e.g", "i.e",
        "inc", "ltd", "co", "corp", "fig", "no", "vol", "pp", "st", "gen",
        "approx", "dept", "est", "al", "fig", "eq",
    }
)


class Segment:
    def __init__(self, text: str, sentence_index: int, paragraph_index: int) -> None:
        self.text = text
        self.sentence_index = sentence_index
        self.paragraph_index = paragraph_index


def split_paragraphs(text: str) -> list[str]:
    paragraphs: list[str] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        cleaned = block.strip()
        if cleaned:
            paragraphs.append(cleaned)
    return paragraphs


def split_sentences(text: str) -> list[str]:
    """Split one paragraph into sentences, preserving the original characters."""

    sentences: list[str] = []
    start = 0
    index = 0
    length = len(text)
    while index < length:
        character = text[index]
        if character in ".!?":
            if _keeps_period(text, index):
                index += 1
                continue
            end = index + 1
            sentence = text[start:end].strip()
            if sentence:
                sentences.append(sentence)
            index = end
            while index < length and text[index].isspace():
                index += 1
            start = index
            continue
        if character == "\n":
            sentence = text[start:index].strip()
            nxt = index + 1
            while nxt < length and text[nxt].isspace() and text[nxt] != "\n":
                nxt += 1
            if sentence and (nxt >= length or text[nxt].isupper() or text[nxt].isdigit()):
                sentences.append(sentence)
                start = index + 1
        index += 1
    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def segment_answer(text: str) -> list[Segment]:
    segments: list[Segment] = []
    sentence_index = 1
    for paragraph_number, paragraph in enumerate(split_paragraphs(text), start=1):
        for sentence in split_sentences(paragraph):
            segments.append(Segment(sentence, sentence_index, paragraph_number))
            sentence_index += 1
    return segments


def _keeps_period(text: str, index: int) -> bool:
    """Return True when the punctuation at index should stay inside a sentence."""

    if text[index] != ".":
        return False
    previous = text[index - 1] if index else ""
    nxt = text[index + 1] if index + 1 < len(text) else ""
    if previous.isdigit() and nxt.isdigit():
        return True
    if previous.isalpha():
        word = _word_before(text, index).lower().rstrip(".")
        if word in _ABBREVIATIONS:
            return True
    return False


def _word_before(text: str, index: int) -> str:
    end = index
    start = index - 1
    while start >= 0 and (text[start].isalnum() or text[start] in ".'"):
        start -= 1
    return text[start + 1 : end]
