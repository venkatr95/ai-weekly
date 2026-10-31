"""Compare each claim with source sentences.

Decisions come from the text of the sources. A missing passage is unsupported,
not contradicted. A percentage that is only implied by two figures is partially
supported, not supported.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from answer_auditor.schemas import EvidenceExcerpt, ExtractedClaim, Passage
from answer_auditor.textutil import format_percent, percentage_change, term_coverage

_CURRENCY = r"(?:€|\$|£|(?:EUR|USD|GBP)\s+)"
_NUMBER = re.compile(
    _CURRENCY + r"?"
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?P<pct>\s*%)?"
    r"(?:\s*(?P<scale>million|billion|thousand|mn|bn))?",
    re.IGNORECASE,
)
_NEGATION = re.compile(
    r"\b(did not|does not|do not|was not|were not|is not|are not|not|no|never|without)\b",
    re.IGNORECASE,
)
_INCREASE = re.compile(
    r"\b(increased|increase|increasing|grew|grown|growth|expanded|expansion|rose|risen|higher|up)\b",
    re.IGNORECASE,
)
_DECREASE = re.compile(
    r"\b(decreased|decrease|decreasing|fell|fallen|reduced|reduction|declined|decline|down|lower|shrank)\b",
    re.IGNORECASE,
)
_METRIC_PATTERNS = (
    ("profit", re.compile(r"\b(net profit|net income|profit|earnings)\b", re.IGNORECASE)),
    ("revenue", re.compile(r"\b(revenue|turnover|sales)\b", re.IGNORECASE)),
    ("hiring", re.compile(r"\b(hired|recruited|new hires)\b", re.IGNORECASE)),
    ("workforce", re.compile(r"\b(workforce|headcount|employees|employee|staff|employed)\b", re.IGNORECASE)),
    ("cost", re.compile(r"\b(costs|cost|expenses|expense)\b", re.IGNORECASE)),
)
_PEOPLE = re.compile(r"\bpeople\b", re.IGNORECASE)
_SCALE = {"million": 1_000_000, "mn": 1_000_000, "billion": 1_000_000_000, "bn": 1_000_000_000, "thousand": 1_000}
_RESTRICTORS = frozenset(
    {
        "europe", "european", "asia", "asian", "america", "american", "domestic",
        "international", "global", "quarterly", "monthly", "q1", "q2", "q3", "q4",
    }
)
_VALUE_TOLERANCE = 0.51


@dataclass
class Quantity:
    kind: str
    value: float
    start: int
    end: int
    symbol: str
    year: int | None = None


@dataclass
class Profile:
    metric: str | None
    direction: str | None
    percents: list[float]
    amounts: list[Quantity]
    years: list[int]
    negated: bool


@dataclass
class Verdict:
    status: str
    explanation: str
    supporting: list[EvidenceExcerpt] = field(default_factory=list)
    contradicting: list[EvidenceExcerpt] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    reason: str = ""


def detect_metrics(text: str) -> set[str]:
    found = {name for name, pattern in _METRIC_PATTERNS if pattern.search(text)}
    if "hiring" in found:
        found.discard("workforce")
    elif _PEOPLE.search(text) and re.search(r"\d", text):
        found.add("workforce")
    return found


def verify_claim(claim: ExtractedClaim, passages: list[Passage]) -> Verdict:
    if claim.claim_type == "opinion":
        return _unverifiable(claim, "The statement is an opinion, so the sources cannot establish it.")
    if claim.claim_type == "recommendation":
        return _unverifiable(claim, "The statement is a recommendation, so the sources cannot establish it.")
    if claim.claim_type == "non_factual":
        return _unverifiable(claim, "The statement is not a factual claim.")
    profile = profile_text(claim.text)
    if profile.direction is None and not profile.amounts and not profile.percents and _is_hedged(claim.text):
        return _unverifiable(
            claim,
            "The statement is hedged and does not give a fact the sources can confirm or contradict.",
        )
    sentences = _unique_passages(passages)
    if profile.direction and profile.percents:
        change = _judge_change(profile, sentences)
        if profile.amounts:
            absolute = _judge_amounts(profile, sentences, claim.text)
            return _combine(change, absolute)
        return change
    if profile.amounts:
        return _judge_amounts(profile, sentences, claim.text)
    return _judge_qualitative(claim.text, profile, sentences)


def profile_text(text: str) -> Profile:
    quantities = _quantities(text)
    years = [int(item.value) for item in quantities if item.kind == "year"]
    percents = [item.value for item in quantities if item.kind == "percent"]
    amounts = [item for item in quantities if item.kind in {"currency", "count"}]
    _attach_years(quantities)
    metric = _primary_metric(text, amounts or [item for item in quantities if item.kind == "percent"])
    direction = _direction(text)
    return Profile(
        metric=metric,
        direction=direction,
        percents=percents,
        amounts=amounts,
        years=years,
        negated=bool(_NEGATION.search(text)),
    )


def _judge_change(profile: Profile, sentences: list[Passage]) -> Verdict:
    claimed = profile.percents[0]
    supports_explicit: list[EvidenceExcerpt] = []
    supports_implied: list[EvidenceExcerpt] = []
    conflicts: list[EvidenceExcerpt] = []
    implied_note = ""
    conflict_note = ""
    for sentence in _compatible(profile, sentences):
        explicit = _explicit_percent(sentence, profile)
        pair = _comparison_pair(sentence.text, profile.metric)
        if explicit is not None:
            quote = _excerpt(sentence)
            if explicit == "match":
                supports_explicit.append(quote)
            else:
                conflicts.append(quote)
                conflict_note = (
                    f"{_label(sentence)} states a percentage that conflicts with the claimed "
                    f"{format_percent(claimed)}%."
                )
            continue
        if pair is None:
            continue
        current, baseline, computed = pair
        if computed is None:
            continue
        computed_direction = "increase" if computed > 0 else "decrease" if computed < 0 else "flat"
        magnitude = abs(computed)
        quote = _excerpt(sentence)
        same_direction = profile.direction == computed_direction
        close = abs(magnitude - claimed) <= _VALUE_TOLERANCE
        rendered = _pair_phrase(sentence, current, baseline)
        if same_direction and close:
            supports_implied.append(quote)
            implied_note = (
                f"{rendered} That is a {format_percent(magnitude)}% {computed_direction}. "
                "The percentage is calculated from those figures and is not stated in the source."
            )
        else:
            conflicts.append(quote)
            if not same_direction and computed_direction != "flat":
                conflict_note = (
                    f"{rendered} That is a {format_percent(magnitude)}% {computed_direction}, "
                    f"which conflicts with a claimed {profile.direction} of {format_percent(claimed)}%."
                )
            else:
                direction_word = computed_direction if computed_direction != "flat" else "change"
                conflict_note = (
                    f"{rendered} That is a {format_percent(magnitude)}% {direction_word}, "
                    f"which conflicts with the claimed {format_percent(claimed)}%."
                )
    return _aggregate_change(
        claimed,
        supports_explicit,
        supports_implied,
        conflicts,
        implied_note,
        conflict_note,
        sentences,
    )


def _aggregate_change(
    claimed: float,
    supports_explicit: list[EvidenceExcerpt],
    supports_implied: list[EvidenceExcerpt],
    conflicts: list[EvidenceExcerpt],
    implied_note: str,
    conflict_note: str,
    sentences: list[Passage],
) -> Verdict:
    has_support = bool(supports_explicit or supports_implied)
    if conflicts and has_support:
        notes = ["The sources disagree on this claim."]
        return Verdict(
            status="partially_supported",
            explanation=conflict_note or "Some sources support the change and others contradict it.",
            supporting=_dedupe(supports_explicit + supports_implied),
            contradicting=_dedupe(conflicts),
            notes=notes,
            reason="source_conflict",
        )
    if supports_explicit and not conflicts:
        return Verdict(
            status="supported",
            explanation=(
                f"{_source_label(supports_explicit[0])} states the {format_percent(claimed)}% change directly."
            ),
            supporting=_dedupe(supports_explicit),
            reason="explicit_match",
        )
    if supports_implied and not conflicts:
        return Verdict(
            status="partially_supported",
            explanation=implied_note,
            supporting=_dedupe(supports_implied),
            notes=["The percentage is implied by the source figures and is not stated directly."],
            reason="implied_calculation",
        )
    if conflicts:
        return Verdict(
            status="contradicted",
            explanation=conflict_note,
            contradicting=_dedupe(conflicts),
            reason="numeric_conflict",
        )
    if not sentences:
        return _unsupported("No supplied source discusses this change. Missing evidence is not a contradiction.")
    return _unsupported(
        "The sources do not state this change or give figures that establish it. "
        "Missing evidence is not a contradiction."
    )


def _judge_amounts(profile: Profile, sentences: list[Passage], claim_text: str) -> Verdict:
    supports: list[EvidenceExcerpt] = []
    conflicts: list[EvidenceExcerpt] = []
    year_mismatches: list[EvidenceExcerpt] = []
    support_bits: list[str] = []
    conflict_bits: list[str] = []
    compatible = _compatible(profile, sentences)
    for amount in profile.amounts:
        amount_supports: list[tuple[Passage, Quantity]] = []
        amount_conflicts: list[tuple[Passage, Quantity]] = []
        other_year: list[tuple[Passage, Quantity]] = []
        for sentence in compatible:
            sentence_supports: list[tuple[Passage, Quantity]] = []
            sentence_conflicts: list[tuple[Passage, Quantity]] = []
            sentence_other_year: list[tuple[Passage, Quantity]] = []
            negated = _polarities_differ(profile.negated, sentence.text)
            for fact in _facts(sentence.text, profile.metric):
                if fact.kind != amount.kind:
                    continue
                year_relation = _year_relation(amount.year, fact.year)
                if negated and _values_close(fact.value, amount.value):
                    sentence_conflicts.append((sentence, fact))
                    continue
                if negated:
                    continue
                if year_relation == "mismatch":
                    if _values_close(fact.value, amount.value):
                        sentence_other_year.append((sentence, fact))
                    continue
                if _values_close(fact.value, amount.value):
                    sentence_supports.append((sentence, fact))
                else:
                    sentence_conflicts.append((sentence, fact))
            # A comparison sentence states the current figure and the baseline.
            # A match on one of those figures is not a contradiction from the other.
            if sentence_supports:
                amount_supports.extend(sentence_supports)
            else:
                amount_conflicts.extend(sentence_conflicts)
                other_year.extend(sentence_other_year)
        if amount_supports and not amount_conflicts:
            sentence, fact = amount_supports[0]
            supports.append(_excerpt(sentence))
            support_bits.append(f"{_label(sentence)} states {_render(fact)} for {profile.metric or 'this fact'}.")
        elif amount_conflicts and not amount_supports:
            sentence, fact = amount_conflicts[0]
            conflicts.append(_excerpt(sentence))
            if _polarities_differ(profile.negated, sentence.text):
                conflict_bits.append(f"{_label(sentence)} denies this claim.")
            else:
                conflict_bits.append(
                    f"{_label(sentence)} states {_render(fact)}, which conflicts with the claimed {_render(amount)}."
                )
        elif amount_supports and amount_conflicts:
            supports.append(_excerpt(amount_supports[0][0]))
            conflicts.append(_excerpt(amount_conflicts[0][0]))
            conflict_bits.append(
                f"The sources disagree: {_label(amount_supports[0][0])} states {_render(amount_supports[0][1])}, "
                f"while {_label(amount_conflicts[0][0])} states {_render(amount_conflicts[0][1])}."
            )
        elif other_year:
            sentence, fact = other_year[0]
            year_mismatches.append(_excerpt(sentence))
            conflict_bits.append(
                f"{_label(sentence)} assigns {_render(fact)} to {fact.year}, not to {amount.year}."
            )
    notes: list[str] = []
    if supports and conflicts:
        notes.append("The sources disagree on this claim.")
        return Verdict(
            status="partially_supported",
            explanation=" ".join(conflict_bits) or "The sources both support and contradict this claim.",
            supporting=_dedupe(supports),
            contradicting=_dedupe(conflicts),
            notes=notes,
            reason="source_conflict",
        )
    if conflicts and not supports:
        return Verdict(
            status="contradicted",
            explanation=" ".join(conflict_bits),
            contradicting=_dedupe(conflicts + year_mismatches),
            reason="numeric_conflict",
        )
    if year_mismatches and not supports:
        return Verdict(
            status="partially_supported",
            explanation=" ".join(conflict_bits),
            contradicting=_dedupe(year_mismatches),
            notes=["The figure appears in the sources, but not for the year in the claim."],
            reason="year_conflict",
        )
    if supports:
        extra = _missing_restrictors_from_text(claim_text, " ".join(item.quote for item in supports))
        if extra:
            return Verdict(
                status="partially_supported",
                explanation=(
                    " ".join(support_bits)
                    + f" The sources do not establish this part of the claim: {', '.join(extra)}."
                ),
                supporting=_dedupe(supports),
                notes=[f"Unsupported scope: {', '.join(extra)}."],
                reason="extra_specificity",
            )
        return Verdict(
            status="supported",
            explanation=" ".join(support_bits) or "The sources state this figure directly.",
            supporting=_dedupe(supports),
            reason="explicit_match",
        )
    if not sentences:
        return _unsupported("No supplied source discusses this claim. Missing evidence is not a contradiction.")
    return _unsupported(
        "The supplied sources do not give enough evidence for this claim. Missing evidence is not a contradiction."
    )


def _judge_qualitative(text: str, profile: Profile, sentences: list[Passage]) -> Verdict:
    best: Passage | None = None
    best_score = 0.0
    for sentence in sentences:
        if profile.metric and detect_metrics(sentence.text) and profile.metric not in detect_metrics(sentence.text):
            continue
        score = term_coverage(text, sentence.text)
        if score > best_score:
            best = sentence
            best_score = score
    if best is None or best_score < 0.4:
        if not sentences:
            return _unsupported("No supplied source discusses this claim. Missing evidence is not a contradiction.")
        return _unsupported(
            "The supplied sources do not give enough evidence for this claim. Missing evidence is not a contradiction."
        )
    quote = _excerpt(best)
    if _polarities_differ(profile.negated, best.text) and best_score >= 0.45:
        return Verdict(
            status="contradicted",
            explanation=f"{_label(best)} contradicts this statement.",
            contradicting=[quote],
            reason="negation",
        )
    claim_years = set(profile.years)
    source_years = {int(item.value) for item in _quantities(best.text) if item.kind == "year"}
    if claim_years and source_years and claim_years.isdisjoint(source_years):
        return Verdict(
            status="contradicted",
            explanation=(
                f"{_label(best)} discusses {', '.join(str(year) for year in sorted(source_years))}, "
                f"not {', '.join(str(year) for year in sorted(claim_years))}."
            ),
            contradicting=[quote],
            reason="year_conflict",
        )
    if best_score >= 0.62:
        extra = _missing_restrictors_from_text(text, best.text)
        if extra:
            return Verdict(
                status="partially_supported",
                explanation=(
                    f"{_label(best)} supports part of this statement, but does not establish: {', '.join(extra)}."
                ),
                supporting=[quote],
                notes=[f"Unsupported scope: {', '.join(extra)}."],
                reason="extra_specificity",
            )
        return Verdict(
            status="supported",
            explanation=f"{_label(best)} states this directly.",
            supporting=[quote],
            reason="qualitative_match",
        )
    return Verdict(
        status="partially_supported",
        explanation=f"{_label(best)} overlaps this statement but does not establish its full wording.",
        supporting=[quote],
        notes=["The match is partial."],
        reason="qualitative_partial",
    )


def _combine(change: Verdict, absolute: Verdict) -> Verdict:
    rank = {
        "contradicted": 4,
        "unsupported": 3,
        "partially_supported": 2,
        "supported": 1,
        "unverifiable": 0,
    }
    if change.status == "unsupported" and absolute.status == "unsupported":
        return change
    if change.status == "supported" and absolute.status == "supported":
        return Verdict(
            status="supported",
            explanation=f"{change.explanation} {absolute.explanation}",
            supporting=_dedupe(change.supporting + absolute.supporting),
            contradicting=_dedupe(change.contradicting + absolute.contradicting),
            notes=_unique_notes(change.notes + absolute.notes),
            reason="explicit_match",
        )
    chosen = change if rank[change.status] >= rank[absolute.status] else absolute
    other = absolute if chosen is change else change
    status = chosen.status
    if "supported" in {change.status, absolute.status} and "contradicted" in {change.status, absolute.status}:
        status = "partially_supported"
    elif status == "supported" and other.status == "partially_supported":
        status = "partially_supported"
    notes = _unique_notes(change.notes + other.notes)
    if status == "partially_supported" and change.reason == "implied_calculation":
        notes.append("The percentage is implied by the source figures and is not stated directly.")
    return Verdict(
        status=status,
        explanation=f"{change.explanation} {absolute.explanation}".strip(),
        supporting=_dedupe(change.supporting + absolute.supporting),
        contradicting=_dedupe(change.contradicting + absolute.contradicting),
        notes=_unique_notes(notes),
        reason=chosen.reason,
    )


def _compatible(profile: Profile, sentences: list[Passage]) -> list[Passage]:
    chosen: list[Passage] = []
    for sentence in sentences:
        metrics = detect_metrics(sentence.text)
        if profile.metric and metrics and profile.metric not in metrics:
            continue
        chosen.append(sentence)
    return chosen


def _facts(text: str, metric: str | None) -> list[Quantity]:
    quantities = _quantities(text)
    _attach_years(quantities)
    metrics = detect_metrics(text)
    if metric and metrics and metric not in metrics:
        return []
    return [item for item in quantities if item.kind in {"currency", "count"}]


def _comparison_pair(
    text: str, metric: str | None
) -> tuple[Quantity, Quantity, float | None] | None:
    facts = _facts(text, metric)
    if len(facts) < 2:
        return None
    compared = re.search(r"\bcompared with\b", text, flags=re.IGNORECASE)
    if compared:
        before = [fact for fact in facts if fact.start < compared.start()]
        after = [fact for fact in facts if fact.start > compared.end()]
        if before and after:
            current, baseline = before[-1], after[0]
            return current, baseline, percentage_change(current.value, baseline.value)
    from_to = re.search(r"\bfrom\b(?P<left>.{0,80}?)\bto\b", text, flags=re.IGNORECASE)
    if from_to:
        left_end = from_to.end()
        baseline_candidates = [fact for fact in facts if from_to.start() < fact.start < left_end]
        current_candidates = [fact for fact in facts if fact.start >= left_end]
        if baseline_candidates and current_candidates:
            baseline, current = baseline_candidates[-1], current_candidates[0]
            return current, baseline, percentage_change(current.value, baseline.value)
    return None


def _explicit_percent(sentence: Passage, profile: Profile) -> str | None:
    if not profile.percents:
        return None
    claimed = profile.percents[0]
    sentence_direction = _direction(sentence.text)
    if profile.direction and sentence_direction and sentence_direction != profile.direction:
        for quantity in _quantities(sentence.text):
            if quantity.kind == "percent" and abs(quantity.value - claimed) <= _VALUE_TOLERANCE:
                return "conflict"
        return None
    for quantity in _quantities(sentence.text):
        if quantity.kind != "percent":
            continue
        if abs(quantity.value - claimed) <= _VALUE_TOLERANCE:
            return "match"
        if sentence_direction or profile.metric in detect_metrics(sentence.text):
            return "conflict"
    return None


def _quantities(text: str) -> list[Quantity]:
    found: list[Quantity] = []
    for match in _NUMBER.finditer(text):
        raw = match.group("num").replace(",", "")
        number = float(raw)
        scale = (match.group("scale") or "").lower()
        prefix = match.group(0)
        symbol = "€" if "€" in prefix or prefix.upper().startswith("EUR") else ""
        if "$" in prefix or prefix.upper().startswith("USD"):
            symbol = "$"
        elif "£" in prefix or prefix.upper().startswith("GBP"):
            symbol = "£"
        if match.group("pct"):
            found.append(Quantity("percent", number, match.start(), match.end(), symbol))
            continue
        if not scale and not symbol and number.is_integer() and 1900 <= int(number) <= 2100:
            found.append(Quantity("year", number, match.start(), match.end(), ""))
            continue
        multiplier = _SCALE.get(scale, 1)
        kind = "currency" if symbol or scale else "count"
        found.append(Quantity(kind, number * multiplier, match.start(), match.end(), symbol or ("€" if scale else "")))
    return found


def _attach_years(quantities: list[Quantity]) -> None:
    years = [item for item in quantities if item.kind == "year"]
    for quantity in quantities:
        if quantity.kind == "year":
            continue
        nearest: Quantity | None = None
        distance = 10**9
        for year in years:
            gap = abs(year.start - quantity.start)
            if gap < distance and gap < 80:
                nearest = year
                distance = gap
        if nearest is not None:
            quantity.year = int(nearest.value)


def _primary_metric(text: str, anchors: list[Quantity]) -> str | None:
    hits: list[tuple[str, int]] = []
    for name, pattern in _METRIC_PATTERNS:
        for match in pattern.finditer(text):
            hits.append((name, match.start()))
    if _PEOPLE.search(text) and re.search(r"\d", text) and not any(name == "hiring" for name, _ in hits):
        for match in _PEOPLE.finditer(text):
            hits.append(("workforce", match.start()))
    if not hits:
        return None
    if any(name == "hiring" for name, _ in hits):
        return "hiring"
    if not anchors:
        return hits[0][0]
    anchor = anchors[0].start
    name, _ = min(hits, key=lambda item: abs(item[1] - anchor))
    return name


def _direction(text: str) -> str | None:
    increase = _INCREASE.search(text)
    decrease = _DECREASE.search(text)
    if increase and decrease:
        return "increase" if increase.start() < decrease.start() else "decrease"
    if increase:
        return "increase"
    if decrease:
        return "decrease"
    return None


def _year_relation(claim_year: int | None, fact_year: int | None) -> str:
    if claim_year is None or fact_year is None:
        return "unknown"
    return "match" if claim_year == fact_year else "mismatch"


def _values_close(left: float, right: float) -> bool:
    return abs(left - right) <= max(0.01, abs(right) * 1e-6)


def _polarities_differ(claim_negated: bool, sentence: str) -> bool:
    return claim_negated != bool(_NEGATION.search(sentence))


def _is_hedged(text: str) -> bool:
    return bool(re.search(r"\b(may have|might have|could have|possibly|appears to)\b", text, re.IGNORECASE))


def _missing_restrictors_from_text(claim: str, evidence: str) -> list[str]:
    evidence_terms = set(re.findall(r"[A-Za-z][\w]+", evidence.lower()))
    missing: list[str] = []
    tokens = re.findall(r"[A-Za-z][\w]+", claim)
    for index, token in enumerate(tokens):
        lowered = token.lower()
        if lowered in _RESTRICTORS and lowered not in evidence_terms:
            missing.append(token)
            continue
        if index > 0 and token[0].isupper() and lowered not in evidence_terms and lowered not in {"the", "a"}:
            if lowered not in {"revenue", "profit", "company"}:
                missing.append(token)
    return _unique_notes(missing)


def _render(quantity: Quantity) -> str:
    if quantity.kind == "percent":
        return f"{format_percent(quantity.value)}%"
    if quantity.kind == "count" and quantity.value >= 1_000_000 and quantity.symbol:
        return _render_scaled(quantity)
    if quantity.value >= 1_000_000 and (quantity.symbol or quantity.value % 1_000_000 == 0):
        return _render_scaled(quantity)
    if quantity.value.is_integer():
        rendered = str(int(quantity.value))
    else:
        rendered = f"{quantity.value:g}"
    return f"{quantity.symbol}{rendered}" if quantity.symbol else rendered


def _render_scaled(quantity: Quantity) -> str:
    if quantity.value % 1_000_000_000 == 0:
        number = f"{quantity.value / 1_000_000_000:.0f} billion"
    elif quantity.value % 1_000_000 == 0:
        number = f"{quantity.value / 1_000_000:.0f} million"
    else:
        number = f"{quantity.value:g}"
    return f"{quantity.symbol}{number}" if quantity.symbol else number


def _pair_phrase(sentence: Passage, current: Quantity, baseline: Quantity) -> str:
    current_year = f" in {current.year}" if current.year else ""
    baseline_year = f" in {baseline.year}" if baseline.year else ""
    return (
        f"{_label(sentence)} reports {_render(current)}{current_year} compared with "
        f"{_render(baseline)}{baseline_year}."
    )


def _excerpt(sentence: Passage) -> EvidenceExcerpt:
    return EvidenceExcerpt(
        source_id=sentence.source_id,
        quote=sentence.text.strip(),
        page=sentence.page,
        source_title=sentence.source_title,
    )


def _label(sentence: Passage) -> str:
    if sentence.source_title:
        return f"{sentence.source_id} ({sentence.source_title})"
    return sentence.source_id


def _source_label(excerpt: EvidenceExcerpt) -> str:
    if excerpt.source_title:
        return f"{excerpt.source_id} ({excerpt.source_title})"
    return excerpt.source_id


def _dedupe(excerpts: list[EvidenceExcerpt]) -> list[EvidenceExcerpt]:
    seen: set[tuple[str, str]] = set()
    unique: list[EvidenceExcerpt] = []
    for excerpt in excerpts:
        key = (excerpt.source_id, " ".join(excerpt.quote.split()).lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(excerpt)
    return unique


def _unique_notes(notes: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for note in notes:
        if note and note not in seen:
            seen.add(note)
            unique.append(note)
    return unique


def _unique_passages(passages: list[Passage]) -> list[Passage]:
    seen: set[tuple[str, str]] = set()
    unique: list[Passage] = []
    for passage in passages:
        key = (passage.source_id, " ".join(passage.text.split()).lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(passage)
    return unique


def _unsupported(explanation: str) -> Verdict:
    return Verdict(status="unsupported", explanation=explanation, reason="no_evidence")


def _unverifiable(claim: ExtractedClaim, explanation: str) -> Verdict:
    del claim
    return Verdict(status="unverifiable", explanation=explanation, reason="not_factual")
