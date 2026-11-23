"""Align corresponding sections between two document versions."""

from __future__ import annotations

from dataclasses import dataclass

from document_detector.section_parser import Section
from document_detector.textutil import jaccard, normalize_for_match


@dataclass
class AlignedPair:
    previous: Section | None
    updated: Section | None
    score: float
    status: str  # matched | added | removed | renamed


def align_sections(previous: list[Section], updated: list[Section]) -> list[AlignedPair]:
    """Greedy best-match alignment by heading similarity and body overlap."""

    used_updated: set[int] = set()
    pairs: list[AlignedPair] = []

    for prev in previous:
        best_index = -1
        best_score = 0.0
        for index, upd in enumerate(updated):
            if index in used_updated:
                continue
            score = _section_score(prev, upd)
            if score > best_score:
                best_score = score
                best_index = index
        if best_index >= 0 and best_score >= 0.35:
            used_updated.add(best_index)
            upd = updated[best_index]
            status = "matched"
            if normalize_for_match(prev.title) != normalize_for_match(upd.title):
                status = "renamed"
            pairs.append(AlignedPair(previous=prev, updated=upd, score=best_score, status=status))
        else:
            pairs.append(AlignedPair(previous=prev, updated=None, score=0.0, status="removed"))

    for index, upd in enumerate(updated):
        if index not in used_updated:
            pairs.append(AlignedPair(previous=None, updated=upd, score=0.0, status="added"))

    return _order_pairs(pairs, previous, updated)


def _section_score(left: Section, right: Section) -> float:
    title_score = jaccard(left.title, right.title)
    if normalize_for_match(left.title) == normalize_for_match(right.title):
        title_score = 1.0
    body_score = jaccard(left.body(), right.body())
    # Prefer title matches; body helps renamed sections.
    return 0.7 * title_score + 0.3 * body_score


def _order_pairs(
    pairs: list[AlignedPair],
    previous: list[Section],
    updated: list[Section],
) -> list[AlignedPair]:
    prev_index = {id(section): index for index, section in enumerate(previous)}
    upd_index = {id(section): index for index, section in enumerate(updated)}

    def sort_key(pair: AlignedPair) -> tuple[int, int]:
        if pair.previous is not None:
            return (0, prev_index.get(id(pair.previous), 10_000))
        if pair.updated is not None:
            return (1, upd_index.get(id(pair.updated), 10_000))
        return (2, 0)

    return sorted(pairs, key=sort_key)
