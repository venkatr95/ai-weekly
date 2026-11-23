"""Heuristic category and importance classification."""

from __future__ import annotations

import re

from document_detector.impact_analyzer import (
    compare_numerical,
    dates_changed,
    obligation_shift,
)
from document_detector.schemas import Category, Importance, NumericalDelta
from document_detector.text_diff import RawChange

_CATEGORY_PATTERNS: list[tuple[Category, re.Pattern[str]]] = [
    ("financial", re.compile(r"\b(salary|compensation|payment|price|fee|cost|budget|invoice|€|\$|£|¥|interest|bonus)\b", re.I)),
    ("dates_deadlines", re.compile(r"\b(deadline|due date|notice period|term|duration|expir|effective date|within \d+)\b", re.I)),
    ("responsibilities", re.compile(r"\b(responsible|shall|must|obligation|duty|owner|accountable)\b", re.I)),
    ("access_permissions", re.compile(r"\b(access|permission|authori[sz]e|credential|login|remote work|work from home)\b", re.I)),
    ("policy", re.compile(r"\b(policy|policies|guideline|code of conduct|compliance)\b", re.I)),
    ("operational", re.compile(r"\b(process|procedure|workflow|delivery|sla|service level)\b", re.I)),
    ("personnel", re.compile(r"\b(employee|employer|manager|director|team|hire|termination|leave)\b", re.I)),
    ("legal_contractual", re.compile(r"\b(agreement|contract|liability|indemnif|warranty|governing law|confidential)\b", re.I)),
    ("numerical", re.compile(r"\d")),
]


def classify_categories(change: RawChange, numerical: NumericalDelta | None) -> list[Category]:
    text = " ".join(filter(None, [change.previous_text, change.updated_text, change.section]))
    found: list[Category] = []
    for category, pattern in _CATEGORY_PATTERNS:
        if pattern.search(text) and category not in found:
            found.append(category)
    if numerical is not None and "numerical" not in found:
        found.insert(0, "numerical")
    if numerical is not None and numerical.currency and "financial" not in found:
        found.insert(0, "financial")
    if dates_changed(change.previous_text, change.updated_text) and "dates_deadlines" not in found:
        found.append("dates_deadlines")
    if obligation_shift(change.previous_text, change.updated_text) and "legal_contractual" not in found:
        found.append("legal_contractual")
    if not found:
        found.append("general")
    return found


def classify_importance(
    change: RawChange,
    categories: list[Category],
    numerical: NumericalDelta | None,
) -> tuple[Importance, str]:
    if change.formatting_only:
        return "informational", "Only whitespace or punctuation formatting differs."

    shift = obligation_shift(change.previous_text, change.updated_text)
    if shift:
        return "high", shift

    if numerical is not None and numerical.direction in {"increased", "decreased"}:
        pct = abs(numerical.percentage_difference or 0)
        unit = (numerical.unit or "").lower()
        if unit in {"day", "week", "month", "year"} and abs(numerical.absolute_difference or 0) >= 30:
            return "high", "A time period changed by a large amount."
        if numerical.currency and pct >= 5:
            return "medium", "A monetary amount changed by at least 5%."
        if unit == "%" and abs(numerical.absolute_difference or 0) >= 1:
            return "medium", "A percentage value changed."
        if pct >= 20 or abs(numerical.absolute_difference or 0) >= 10:
            return "high", "A numerical value changed substantially."
        return "medium", "A numerical value changed."

    if dates_changed(change.previous_text, change.updated_text):
        return "high", "A date or deadline wording changed."

    if change.change_type in {"added", "removed"}:
        if any(cat in categories for cat in ("financial", "legal_contractual", "dates_deadlines", "access_permissions")):
            return "high", f"A {change.change_type} passage affects a sensitive category."
        return "medium", f"A section or paragraph was {change.change_type}."

    sensitive = {"financial", "legal_contractual", "dates_deadlines", "access_permissions", "responsibilities"}
    if sensitive.intersection(categories):
        return "high", "Wording changed in a category that often affects obligations or entitlements."

    prev = change.previous_text or ""
    upd = change.updated_text or ""
    if abs(len(prev) - len(upd)) < 8 and prev.lower() != upd.lower():
        return "low", "A small wording change was detected."
    return "medium", "Substantive wording differs between versions."


def default_title(change: RawChange, numerical: NumericalDelta | None) -> str:
    section = change.section or "Document"
    if numerical and numerical.direction in {"increased", "decreased"}:
        if numerical.currency:
            label = numerical.currency
        elif numerical.unit == "day":
            label = "days"
        elif numerical.unit:
            label = f"{numerical.unit}s" if not numerical.unit.endswith("s") else numerical.unit
        else:
            label = "value"
        return f"{section}: {label} {numerical.direction}"
    if change.change_type == "added":
        return f"{section}: content added"
    if change.change_type == "removed":
        return f"{section}: content removed"
    return f"{section}: wording modified"


def default_explanation(change: RawChange, numerical: NumericalDelta | None) -> str:
    if change.formatting_only:
        return "The text is effectively the same after normalizing whitespace and punctuation."
    if numerical and numerical.previous_value is not None and numerical.updated_value is not None:
        parts = [
            f"The value changed from {numerical.previous_value} to {numerical.updated_value}"
        ]
        if numerical.currency:
            parts[0] += f" {numerical.currency}"
        elif numerical.unit:
            parts[0] += f" {numerical.unit}"
        parts[0] += "."
        if numerical.absolute_difference is not None:
            parts.append(f"Absolute difference: {numerical.absolute_difference}.")
        if numerical.percentage_difference is not None:
            parts.append(f"Percentage difference: {numerical.percentage_difference}%.")
        return " ".join(parts)
    shift = obligation_shift(change.previous_text, change.updated_text)
    if shift:
        return shift
    if change.change_type == "added":
        return "This text appears in the updated document and not in the previous version."
    if change.change_type == "removed":
        return "This text appears in the previous document and not in the updated version."
    return "The wording differs between the previous and updated versions."


def default_impact(change: RawChange, numerical: NumericalDelta | None, importance: Importance) -> str:
    if change.formatting_only or importance == "informational":
        return "No substantive practical impact is apparent from the text alone."
    if numerical and numerical.direction == "increased":
        return "The updated figure is higher than before; confirm whether that matches the intended terms."
    if numerical and numerical.direction == "decreased":
        return "The updated figure is lower than before; confirm whether that matches the intended terms."
    shift = obligation_shift(change.previous_text, change.updated_text)
    if shift:
        return "The practical strength of the obligation may have changed; a human reviewer should confirm intent."
    if change.change_type == "added":
        return "New obligations, entitlements, or facts may have been introduced."
    if change.change_type == "removed":
        return "Previously stated obligations, entitlements, or facts may no longer apply."
    return "Interpretation or execution of this section may change; significance cannot be determined beyond the quoted text."


def default_recommendation(importance: Importance, change: RawChange) -> str:
    if importance in {"critical", "high"}:
        return f"Review the change in '{change.section or 'this section'}' before relying on the updated document."
    if importance == "medium":
        return "Skim this change and confirm it matches the intended update."
    if importance == "low":
        return "Optional review; impact appears limited from the text alone."
    return "No action needed beyond noting a formatting difference."


def enrich_raw_change(change: RawChange) -> dict:
    numerical = compare_numerical(change.previous_text, change.updated_text)
    categories = classify_categories(change, numerical)
    importance, reason = classify_importance(change, categories, numerical)
    return {
        "categories": categories,
        "importance": importance,
        "importance_reason": reason,
        "title": default_title(change, numerical),
        "explanation": default_explanation(change, numerical),
        "impact": default_impact(change, numerical, importance),
        "recommendation": default_recommendation(importance, change),
        "numerical": numerical,
    }
