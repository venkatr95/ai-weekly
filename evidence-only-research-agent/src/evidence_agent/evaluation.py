"""Gold-set evaluation for retrieval, citations, abstention, and conflicts.

The metrics describe this corpus and this provider. They are not a claim that
the system is hallucination-free.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from pydantic import BaseModel, Field

from evidence_agent.pipeline import ResearchPipeline
from evidence_agent.schemas import AnswerResponse


class GoldQuestion(BaseModel):
    id: str
    question: str
    type: str
    relevant_sources: list[str] = Field(default_factory=list)
    required_phrases: list[str] = Field(default_factory=list)
    phrase_match: str = "all"
    expected_abstain: bool = False
    expect_conflict: bool = False
    forbidden_phrases: list[str] = Field(default_factory=list)
    expected_page: int | None = None


class QuestionResult(BaseModel):
    id: str
    type: str
    retrieved_sources: list[str]
    recall_hit: bool | None = None
    citation_validity: float | None = None
    citation_support: float | None = None
    phrases_hit: bool | None = None
    abstained: bool
    abstention_correct: bool | None = None
    conflict_detected: bool
    conflict_correct: bool | None = None
    forbidden_hit: bool = False
    page_correct: bool | None = None
    latency_seconds: float


class EvaluationReport(BaseModel):
    questions: int
    retrieval_recall_at_k: float | None
    citation_validity: float | None
    citation_support_rate: float | None
    claim_coverage: float | None
    abstention_precision: float | None
    abstention_recall: float | None
    conflict_recall: float | None
    conflict_false_positive_rate: float | None
    mean_latency_seconds: float
    provider: str
    retrieval_k: int
    notes: list[str]
    results: list[QuestionResult]


def load_questions(path: Path) -> list[GoldQuestion]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [GoldQuestion.model_validate(item) for item in payload]


def evaluate(pipeline: ResearchPipeline, documents: Path, questions: list[GoldQuestion], k: int | None = None) -> EvaluationReport:
    pipeline.index_path(documents, rebuild=True)
    retrieval_k = k or pipeline.settings.retrieval_k
    results: list[QuestionResult] = []
    for item in questions:
        started = time.perf_counter()
        response, passages = pipeline.ask(item.question, k=retrieval_k)
        latency = time.perf_counter() - started
        results.append(_score(item, response, passages, latency))
    return _aggregate(results, pipeline.settings.generation_provider, retrieval_k)


def _score(item: GoldQuestion, response: AnswerResponse, passages, latency: float) -> QuestionResult:
    retrieved = []
    for passage in passages:
        if passage.relative_path not in retrieved:
            retrieved.append(passage.relative_path)
    recall_hit = None
    if item.relevant_sources:
        recall_hit = any(source in retrieved for source in item.relevant_sources)
    validity = None
    support = None
    if response.citations:
        validity = sum(1 for citation in response.citations if citation.valid) / len(response.citations)
        support = sum(1 for citation in response.citations if citation.supports_claim) / len(response.citations)
    phrases_hit = None
    if item.required_phrases:
        blob = "\n".join([claim.text for claim in response.claims] + [citation.excerpt for citation in response.citations])
        hits = [phrase.lower() in blob.lower() for phrase in item.required_phrases]
        phrases_hit = all(hits) if item.phrase_match != "any" else any(hits)
    abstention_correct = None
    if item.expected_abstain or response.abstained:
        abstention_correct = response.abstained == item.expected_abstain
    conflict_detected = bool(response.conflicts)
    forbidden_blob = " ".join(
        [response.answer, *[claim.text for claim in response.claims], *[item.detail for item in response.unanswered_questions]]
    ).lower()
    forbidden_hit = any(phrase.lower() in forbidden_blob for phrase in item.forbidden_phrases)
    page_correct = None
    if item.expected_page is not None and item.relevant_sources:
        page_correct = any(
            citation.page == item.expected_page and citation.source_path in item.relevant_sources
            for citation in response.citations
        )
    return QuestionResult(
        id=item.id,
        type=item.type,
        retrieved_sources=retrieved,
        recall_hit=recall_hit,
        citation_validity=validity,
        citation_support=support,
        phrases_hit=phrases_hit,
        abstained=response.abstained,
        abstention_correct=abstention_correct,
        conflict_detected=conflict_detected,
        conflict_correct=conflict_detected == item.expect_conflict,
        forbidden_hit=forbidden_hit,
        page_correct=page_correct,
        latency_seconds=latency,
    )


def _aggregate(results: list[QuestionResult], provider: str, retrieval_k: int) -> EvaluationReport:
    def mean(values: list[float]) -> float | None:
        if not values:
            return None
        return sum(values) / len(values)

    recall_values = [1.0 if result.recall_hit else 0.0 for result in results if result.recall_hit is not None]
    validity_values = [result.citation_validity for result in results if result.citation_validity is not None]
    support_values = [result.citation_support for result in results if result.citation_support is not None]
    coverage_values = [1.0 if result.phrases_hit else 0.0 for result in results if result.phrases_hit is not None]
    expected_abstain = [result for result in results if _expects_abstain(result)]
    abstained = [result for result in results if result.abstained]
    abstention_recall = None
    if expected_abstain:
        abstention_recall = sum(1 for result in expected_abstain if result.abstained) / len(expected_abstain)
    abstention_precision = None
    if abstained:
        abstention_precision = sum(1 for result in abstained if result.abstention_correct) / len(abstained)
    return EvaluationReport(
        questions=len(results),
        retrieval_recall_at_k=mean(recall_values),
        citation_validity=mean([float(value) for value in validity_values]),
        citation_support_rate=mean([float(value) for value in support_values]),
        claim_coverage=mean(coverage_values),
        abstention_precision=abstention_precision,
        abstention_recall=abstention_recall,
        conflict_recall=_conflict_recall(results),
        conflict_false_positive_rate=_conflict_false_positive_rate(results),
        mean_latency_seconds=mean([result.latency_seconds for result in results]) or 0.0,
        provider=provider,
        retrieval_k=retrieval_k,
        notes=[
            "Scores are computed on the bundled synthetic corpus with the configured provider.",
            "Citation validity checks that an excerpt occurs in the indexed chunk. It does not prove the corpus is correct.",
            "No remote-model cost is incurred when the provider is extractive.",
        ],
        results=results,
    )


def _expects_abstain(result: QuestionResult) -> bool:
    return result.type == "unanswerable"


def _conflict_recall(results: list[QuestionResult]) -> float | None:
    relevant = [result for result in results if result.type == "contradictory"]
    if not relevant:
        return None
    return sum(1 for result in relevant if result.conflict_detected) / len(relevant)


def _conflict_false_positive_rate(results: list[QuestionResult]) -> float | None:
    relevant = [result for result in results if result.type != "contradictory"]
    if not relevant:
        return None
    return sum(1 for result in relevant if result.conflict_detected) / len(relevant)


def format_report(report: EvaluationReport) -> str:
    def pct(value: float | None) -> str:
        if value is None:
            return "n/a"
        return f"{value:.3f}"

    lines = [
        f"Questions: {report.questions}",
        f"Provider: {report.provider}",
        f"Retrieval k: {report.retrieval_k}",
        f"Retrieval recall@k: {pct(report.retrieval_recall_at_k)}",
        f"Citation validity: {pct(report.citation_validity)}",
        f"Citation support rate: {pct(report.citation_support_rate)}",
        f"Claim coverage: {pct(report.claim_coverage)}",
        f"Abstention precision: {pct(report.abstention_precision)}",
        f"Abstention recall: {pct(report.abstention_recall)}",
        f"Conflict recall: {pct(report.conflict_recall)}",
        f"Conflict false-positive rate: {pct(report.conflict_false_positive_rate)}",
        f"Mean latency seconds: {report.mean_latency_seconds:.4f}",
        "",
        "Per question:",
    ]
    for result in report.results:
        lines.append(
            f"- {result.id}: abstained={result.abstained} conflict={result.conflict_detected} "
            f"recall={result.recall_hit} phrases={result.phrases_hit} forbidden={result.forbidden_hit} "
            f"page={result.page_correct}"
        )
    return "\n".join(lines) + "\n"
