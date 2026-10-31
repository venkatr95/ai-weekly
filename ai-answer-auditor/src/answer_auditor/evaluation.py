"""Score the deterministic auditor against manually labeled examples.

The labels are the judge. The same model is not asked to grade its own output.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from answer_auditor.config import Settings
from answer_auditor.pipeline import audit
from answer_auditor.schemas import AuditReport
from answer_auditor.textutil import locate_quote


class BenchmarkCase(BaseModel):
    id: str
    answer: str
    sources: list[dict]
    question: str | None = None
    expected_statuses: list[str]
    expected_claim_substrings: list[str] = Field(default_factory=list)


class CaseScore(BaseModel):
    id: str
    passed: bool
    status_match: bool
    expected_statuses: list[str]
    actual_statuses: list[str]
    citation_failures: int = 0
    notes: list[str] = Field(default_factory=list)


class EvaluationReport(BaseModel):
    cases: int
    passed: int
    verification_accuracy: float
    citation_validity: float
    results: list[CaseScore]


def load_benchmark(path: Path) -> list[BenchmarkCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [BenchmarkCase.model_validate(item) for item in payload]


def evaluate_benchmark(path: Path, settings: Settings | None = None) -> EvaluationReport:
    cases = load_benchmark(path)
    active = settings or Settings(provider="heuristic")
    results: list[CaseScore] = []
    citation_checks = 0
    citation_failures = 0
    for case in cases:
        report = audit(case.answer, case.sources, question=case.question, settings=active)
        score, checks, failures = _score_case(case, report)
        results.append(score)
        citation_checks += checks
        citation_failures += failures
    passed = sum(1 for result in results if result.passed)
    status_hits = sum(1 for result in results if result.status_match)
    accuracy = round(100.0 * status_hits / len(results), 1) if results else 0.0
    validity = 100.0 if citation_checks == 0 else round(100.0 * (citation_checks - citation_failures) / citation_checks, 1)
    return EvaluationReport(
        cases=len(results),
        passed=passed,
        verification_accuracy=accuracy,
        citation_validity=validity,
        results=results,
    )


def _benchmark_text(case: BenchmarkCase) -> dict[str, str]:
    texts: dict[str, str] = {}
    for index, source in enumerate(case.sources, start=1):
        text = source.get("text")
        if not isinstance(text, str):
            continue
        source_id = source.get("source_id") or source.get("id") or f"S{index}"
        if isinstance(source_id, str):
            texts[source_id] = text
    return texts


def _score_case(case: BenchmarkCase, report: AuditReport) -> tuple[CaseScore, int, int]:
    actual = [claim.status for claim in report.claims]
    notes: list[str] = []
    if actual != case.expected_statuses:
        notes.append("Statuses differ from the labeled example.")
    claim_text = " ".join(claim.text for claim in report.claims).lower()
    for snippet in case.expected_claim_substrings:
        if snippet.lower() not in claim_text:
            notes.append(f"Missing claim text: {snippet}")
    failures = 0
    checks = 0
    source_text = _benchmark_text(case)
    documents = {source.source_id: source for source in report.sources}
    for claim in report.claims:
        for excerpt in [*claim.supporting_evidence, *claim.contradicting_evidence]:
            checks += 1
            if excerpt.source_id not in documents:
                failures += 1
                notes.append(f"{claim.claim_id} cites unknown source {excerpt.source_id}.")
            if not excerpt.quote.strip():
                failures += 1
                notes.append(f"{claim.claim_id} has an empty quotation.")
            text = source_text.get(excerpt.source_id)
            if text is not None and locate_quote(text, excerpt.quote) is None:
                failures += 1
                notes.append(f"{claim.claim_id} quotes text that is not in {excerpt.source_id}.")
    status_notes = [note for note in notes if note.startswith("Statuses") or note.startswith("Missing claim")]
    return (
        CaseScore(
            id=case.id,
            passed=not notes,
            status_match=not status_notes,
            expected_statuses=case.expected_statuses,
            actual_statuses=actual,
            citation_failures=failures,
            notes=notes,
        ),
        checks,
        failures,
    )
