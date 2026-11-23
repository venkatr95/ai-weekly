"""Deterministic textual difference detection."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from document_detector.document_aligner import AlignedPair
from document_detector.textutil import collapse_spaces, normalize_for_match

_WORD = re.compile(r"\S+|\s+")


@dataclass
class RawChange:
    change_type: str
    previous_text: str | None
    updated_text: str | None
    section: str | None
    previous_section: str | None
    updated_section: str | None
    previous_page: int | None
    updated_page: int | None
    formatting_only: bool = False


def diff_aligned_sections(pairs: list[AlignedPair]) -> list[RawChange]:
    changes: list[RawChange] = []
    for pair in pairs:
        if pair.status == "added" and pair.updated is not None:
            text = pair.updated.full_text().strip()
            if text:
                changes.append(
                    RawChange(
                        change_type="added",
                        previous_text=None,
                        updated_text=text,
                        section=pair.updated.title,
                        previous_section=None,
                        updated_section=pair.updated.title,
                        previous_page=None,
                        updated_page=pair.updated.page,
                    )
                )
            continue
        if pair.status == "removed" and pair.previous is not None:
            text = pair.previous.full_text().strip()
            if text:
                changes.append(
                    RawChange(
                        change_type="removed",
                        previous_text=text,
                        updated_text=None,
                        section=pair.previous.title,
                        previous_section=pair.previous.title,
                        updated_section=None,
                        previous_page=pair.previous.page,
                        updated_page=None,
                    )
                )
            continue
        if pair.previous is None or pair.updated is None:
            continue
        changes.extend(_diff_section_pair(pair))
    return _merge_trivial(changes)


def _diff_section_pair(pair: AlignedPair) -> list[RawChange]:
    assert pair.previous is not None and pair.updated is not None
    prev_paras = [p.text.strip() for p in pair.previous.paragraphs if p.text.strip()]
    upd_paras = [p.text.strip() for p in pair.updated.paragraphs if p.text.strip()]
    section_title = pair.updated.title if pair.status != "renamed" else pair.updated.title

    if not prev_paras and not upd_paras:
        if pair.status == "renamed":
            return [
                RawChange(
                    change_type="modified",
                    previous_text=pair.previous.title,
                    updated_text=pair.updated.title,
                    section=section_title,
                    previous_section=pair.previous.title,
                    updated_section=pair.updated.title,
                    previous_page=pair.previous.page,
                    updated_page=pair.updated.page,
                )
            ]
        return []

    matcher = difflib.SequenceMatcher(a=prev_paras, b=upd_paras, autojunk=False)
    changes: list[RawChange] = []
    if pair.status == "renamed":
        changes.append(
            RawChange(
                change_type="modified",
                previous_text=f"Section heading: {pair.previous.title}",
                updated_text=f"Section heading: {pair.updated.title}",
                section=section_title,
                previous_section=pair.previous.title,
                updated_section=pair.updated.title,
                previous_page=pair.previous.page,
                updated_page=pair.updated.page,
            )
        )

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "insert":
            for paragraph in upd_paras[j1:j2]:
                changes.append(
                    RawChange(
                        change_type="added",
                        previous_text=None,
                        updated_text=paragraph,
                        section=section_title,
                        previous_section=pair.previous.title,
                        updated_section=pair.updated.title,
                        previous_page=pair.previous.page,
                        updated_page=pair.updated.page,
                    )
                )
        elif tag == "delete":
            for paragraph in prev_paras[i1:i2]:
                changes.append(
                    RawChange(
                        change_type="removed",
                        previous_text=paragraph,
                        updated_text=None,
                        section=section_title,
                        previous_section=pair.previous.title,
                        updated_section=pair.updated.title,
                        previous_page=pair.previous.page,
                        updated_page=pair.updated.page,
                    )
                )
        else:
            left = prev_paras[i1:i2]
            right = upd_paras[j1:j2]
            # Pair replaced paragraphs one-to-one when lengths match.
            if len(left) == len(right):
                for previous_text, updated_text in zip(left, right):
                    changes.append(_paragraph_change(pair, previous_text, updated_text, section_title))
            else:
                changes.append(
                    RawChange(
                        change_type="modified",
                        previous_text="\n\n".join(left) or None,
                        updated_text="\n\n".join(right) or None,
                        section=section_title,
                        previous_section=pair.previous.title,
                        updated_section=pair.updated.title,
                        previous_page=pair.previous.page,
                        updated_page=pair.updated.page,
                        formatting_only=_formatting_only("\n\n".join(left), "\n\n".join(right)),
                    )
                )
    return changes


def _paragraph_change(
    pair: AlignedPair,
    previous_text: str,
    updated_text: str,
    section_title: str,
) -> RawChange:
    assert pair.previous is not None and pair.updated is not None
    formatting = _formatting_only(previous_text, updated_text)
    return RawChange(
        change_type="modified",
        previous_text=previous_text,
        updated_text=updated_text,
        section=section_title,
        previous_section=pair.previous.title,
        updated_section=pair.updated.title,
        previous_page=pair.previous.page,
        updated_page=pair.updated.page,
        formatting_only=formatting,
    )


def _formatting_only(previous: str, updated: str) -> bool:
    return normalize_for_match(previous) == normalize_for_match(updated) and previous != updated


def word_diff(previous: str, updated: str) -> tuple[str, str]:
    left = _WORD.findall(previous)
    right = _WORD.findall(updated)
    matcher = difflib.SequenceMatcher(a=left, b=right, autojunk=False)
    prev_bits: list[str] = []
    upd_bits: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            prev_bits.extend(left[i1:i2])
            upd_bits.extend(right[j1:j2])
        elif tag == "delete":
            prev_bits.append("[-" + "".join(left[i1:i2]) + "-]")
        elif tag == "insert":
            upd_bits.append("[+" + "".join(right[j1:j2]) + "+]")
        else:
            prev_bits.append("[-" + "".join(left[i1:i2]) + "-]")
            upd_bits.append("[+" + "".join(right[j1:j2]) + "+]")
    return "".join(prev_bits), "".join(upd_bits)


def _merge_trivial(changes: list[RawChange]) -> list[RawChange]:
    result: list[RawChange] = []
    for change in changes:
        if change.change_type == "modified":
            prev = collapse_spaces(change.previous_text or "")
            upd = collapse_spaces(change.updated_text or "")
            if prev == upd:
                continue
            change.previous_text = prev or None
            change.updated_text = upd or None
        result.append(change)
    return result
