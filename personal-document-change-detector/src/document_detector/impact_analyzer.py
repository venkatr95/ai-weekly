"""Detect numerical and date changes from paired texts."""

from __future__ import annotations

import re
from dataclasses import dataclass

from document_detector.schemas import NumericalDelta

_CURRENCY = r"(?:€|\$|£|¥|USD|EUR|GBP)"
_NUMBER = r"(?:-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?)"
_WORD_NUMBER = (
    r"zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
    r"thirty|forty|fifty|sixty|seventy|eighty|ninety"
)
_AMOUNT = re.compile(
    rf"(?P<currency>{_CURRENCY})?\s*(?P<value>{_NUMBER})\s*(?P<currency2>{_CURRENCY})?\s*"
    rf"(?P<unit>%|percent|days?|weeks?|months?|years?|hours?)?",
    re.IGNORECASE,
)
_WORD_AMOUNT = re.compile(
    rf"\b(?P<value>{_WORD_NUMBER})\b\s+(?P<unit>days?|weeks?|months?|years?|hours?)\b",
    re.IGNORECASE,
)
_DATE = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r"|\d{4}-\d{2}-\d{2}"
    r"|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+\d{1,2},?\s+\d{4})\b",
    re.IGNORECASE,
)
_OBLIGATION = re.compile(r"\b(shall|must|will|should|may|aim to|endeavo(?:u)?r to)\b", re.IGNORECASE)
_WORD_VALUES = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}


@dataclass
class ValueHit:
    value: float
    raw: str
    currency: str | None
    unit: str | None
    start: int
    end: int


def extract_amounts(text: str) -> list[ValueHit]:
    hits: list[ValueHit] = []
    for match in _AMOUNT.finditer(text or ""):
        raw_value = match.group("value").replace(",", "")
        try:
            value = float(raw_value)
        except ValueError:
            continue
        currency = match.group("currency") or match.group("currency2")
        unit = match.group("unit")
        if unit:
            unit = unit.lower().rstrip("s")
            if unit == "percent":
                unit = "%"
        hits.append(
            ValueHit(
                value=value,
                raw=match.group(0).strip(),
                currency=currency,
                unit=unit,
                start=match.start(),
                end=match.end(),
            )
        )
    for match in _WORD_AMOUNT.finditer(text or ""):
        value = float(_WORD_VALUES[match.group("value").lower()])
        unit = match.group("unit").lower().rstrip("s")
        hits.append(
            ValueHit(
                value=value,
                raw=match.group(0).strip(),
                currency=None,
                unit=unit,
                start=match.start(),
                end=match.end(),
            )
        )
    return hits


def extract_dates(text: str) -> list[str]:
    return [match.group(0) for match in _DATE.finditer(text or "")]


def compare_numerical(previous: str | None, updated: str | None) -> NumericalDelta | None:
    left = extract_amounts(previous or "")
    right = extract_amounts(updated or "")
    if not left or not right:
        return None

    # Prefer pairs that share currency/unit context.
    best: tuple[ValueHit, ValueHit] | None = None
    for prev in left:
        for upd in right:
            if prev.value == upd.value and (prev.currency or "") == (upd.currency or "") and (prev.unit or "") == (
                upd.unit or ""
            ):
                continue
            if best is None:
                best = (prev, upd)
                continue
            same_unit = (prev.unit or "") == (upd.unit or "")
            same_currency = (prev.currency or "") == (upd.currency or "")
            best_same = (best[0].unit or "") == (best[1].unit or "") and (best[0].currency or "") == (
                best[1].currency or ""
            )
            if (same_unit or same_currency) and not best_same:
                best = (prev, upd)
            elif abs(prev.value - upd.value) > abs(best[0].value - best[1].value) and (same_unit or same_currency):
                best = (prev, upd)

    if best is None:
        # All values identical under shared units.
        return None

    prev, upd = best
    if (prev.unit or "") != (upd.unit or "") and (prev.currency or "") != (upd.currency or ""):
        # Incompatible units/currencies — report values without percentage.
        direction = "unknown"
        if prev.value < upd.value:
            direction = "increased"
        elif prev.value > upd.value:
            direction = "decreased"
        return NumericalDelta(
            kind="value",
            previous_value=prev.value,
            updated_value=upd.value,
            unit=upd.unit or prev.unit,
            currency=upd.currency or prev.currency,
            absolute_difference=round(upd.value - prev.value, 6),
            percentage_difference=None,
            direction=direction,
        )

    absolute = round(upd.value - prev.value, 6)
    percentage = None
    if prev.value != 0:
        percentage = round(100.0 * absolute / abs(prev.value), 2)
    if absolute > 0:
        direction = "increased"
    elif absolute < 0:
        direction = "decreased"
    else:
        direction = "unchanged"
    kind = "percentage" if (upd.unit or prev.unit) == "%" else "currency" if (upd.currency or prev.currency) else "value"
    return NumericalDelta(
        kind=kind,
        previous_value=prev.value,
        updated_value=upd.value,
        unit=upd.unit or prev.unit,
        currency=upd.currency or prev.currency,
        absolute_difference=absolute,
        percentage_difference=percentage,
        direction=direction,
    )


def obligation_shift(previous: str | None, updated: str | None) -> str | None:
    left = {m.group(1).lower() for m in _OBLIGATION.finditer(previous or "")}
    right = {m.group(1).lower() for m in _OBLIGATION.finditer(updated or "")}
    if not left and not right:
        return None
    strong = {"shall", "must", "will"}
    weak = {"should", "may", "aim to", "endeavor to", "endeavour to"}
    left_strong = bool(left & strong)
    right_strong = bool(right & strong)
    left_weak = bool(left & weak)
    right_weak = bool(right & weak)
    if left_strong and right_weak and not right_strong:
        return "Obligation strength appears weakened."
    if left_weak and right_strong and not left_strong:
        return "Obligation strength appears strengthened."
    if left != right:
        return "Modal wording changed."
    return None


def dates_changed(previous: str | None, updated: str | None) -> bool:
    return set(extract_dates(previous or "")) != set(extract_dates(updated or ""))
