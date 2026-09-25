"""Measure retrieval, citation, grounding, and refusal on the sample corpus.

Uses the offline hashing embedder and the extractive answerer so the numbers do
not depend on an API key. The same chunk size as the API (500 / 100) is used.

    py evaluation/run_eval.py
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import make_settings
from app.pipeline import build_pipeline
from app.schemas.answer import INSUFFICIENT_ANSWER
from app.textutil import numbers_in, overlap_hits

CORPUS = ROOT / "evaluation" / "corpus"
QUESTIONS = ROOT / "evaluation" / "questions.jsonl"
METRICS = ROOT / "evaluation" / "metrics.json"

RETRIEVAL_RECALL_TARGET = 0.90
CITATION_ACCURACY_TARGET = 0.95
GROUNDED_ANSWER_RATE_TARGET = 0.95
UNSUPPORTED_REFUSAL_TARGET = 1.0

_MARKER = re.compile(r"\[(\d+)\]")


def evaluate() -> dict:
    settings = make_settings(
        vector_store="memory",
        embedding_provider="hashing",
        llm_provider="extractive",
        chunk_size_tokens=500,
        chunk_overlap_tokens=100,
        top_k=5,
        rerank_pool_multiplier=6,
    )
    pipeline = build_pipeline(settings)
    handbook_chunks = 0
    for path in sorted(CORPUS.glob("*.md")):
        uploaded = pipeline.ingest(path.name, path.read_bytes(), "text/markdown")
        if path.name == "employee-handbook.md":
            handbook_chunks = uploaded.chunks

    questions = [
        json.loads(line)
        for line in QUESTIONS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rows: list[dict] = []
    citation_good = 0
    citation_total = 0
    for question in questions:
        response = pipeline.answer(question["question"], debug=True)
        retrieved = response.retrieved or []
        row = _score_question(question, response.answer, list(response.citations), retrieved)
        citation_good += row.pop("citation_good")
        citation_total += row.pop("citation_total")
        rows.append(row)

    answerable = [row for row in rows if row["expect"] == "answer"]
    unsupported = [row for row in rows if row["expect"] == "insufficient"]
    report = {
        "questions": len(rows),
        "handbook_chunks": handbook_chunks,
        "retrieval_recall": _rate(sum(row["retrieval_hit"] for row in answerable), len(answerable)),
        "citation_accuracy": _rate(citation_good, citation_total),
        "grounded_answer_rate": _rate(sum(row["grounded"] for row in answerable), len(answerable)),
        "unsupported_refusal_rate": _rate(sum(row["refused"] for row in unsupported), len(unsupported)),
        "targets": {
            "retrieval_recall": RETRIEVAL_RECALL_TARGET,
            "citation_accuracy": CITATION_ACCURACY_TARGET,
            "grounded_answer_rate": GROUNDED_ANSWER_RATE_TARGET,
            "unsupported_refusal_rate": UNSUPPORTED_REFUSAL_TARGET,
        },
        "results": rows,
    }
    report["passed"] = (
        report["retrieval_recall"] >= RETRIEVAL_RECALL_TARGET
        and report["citation_accuracy"] >= CITATION_ACCURACY_TARGET
        and report["grounded_answer_rate"] >= GROUNDED_ANSWER_RATE_TARGET
        and report["unsupported_refusal_rate"] >= UNSUPPORTED_REFUSAL_TARGET
        and handbook_chunks >= 2
        and len(rows) >= 15
    )
    return report


def _score_question(question: dict, answer: str, citations: list, retrieved: list) -> dict:
    snippets = question["snippets"]
    retrieval_hit = all(_snippet_in(snippet, retrieved) for snippet in snippets)
    distinct = True
    if question["type"] == "multi_chunk" and len(snippets) >= 2:
        first = _chunk_ids(snippets[0], retrieved)
        second = _chunk_ids(snippets[1], retrieved)
        distinct = bool(first and second and first.isdisjoint(second))
        retrieval_hit = retrieval_hit and distinct

    good, total = _citation_pairs(answer, citations, retrieved)
    filenames = {citation.document for citation in citations}
    expected_files = set(question.get("citation_filenames") or [])
    files_ok = expected_files <= filenames
    snippets_cited = all(_snippet_in(snippet, _cited_chunks(citations, retrieved)) for snippet in snippets)
    grounded = (
        question["expect"] == "answer"
        and answer != INSUFFICIENT_ANSWER
        and bool(citations)
        and snippets_cited
        and files_ok
        and total > 0
        and good == total
    )
    refused = answer == INSUFFICIENT_ANSWER and not citations
    reasons: list[str] = []
    if question["expect"] == "answer" and not distinct:
        reasons.append("snippets were not found in different chunks")
    elif question["expect"] == "answer" and not retrieval_hit:
        reasons.append("expected snippet missing from top-k")
    if question["expect"] == "answer" and not grounded:
        reasons.append("answer was not grounded in the cited chunks")
    if question["expect"] == "insufficient" and not refused:
        reasons.append("unsupported question was not refused")
    return {
        "id": question["id"],
        "type": question["type"],
        "expect": question["expect"],
        "answer": answer,
        "best_score": retrieved[0].score if retrieved else 0.0,
        "retrieval_hit": retrieval_hit,
        "grounded": grounded if question["expect"] == "answer" else False,
        "refused": refused,
        "distinct_chunks": distinct,
        "reasons": reasons,
        "citation_good": good if question["expect"] == "answer" else 0,
        "citation_total": total if question["expect"] == "answer" else 0,
    }


def _snippet_in(snippet: dict, chunks: list) -> bool:
    return any(
        chunk.filename == snippet["filename"] and snippet["text"] in chunk.text for chunk in chunks
    )


def _chunk_ids(snippet: dict, chunks: list) -> set[str]:
    return {
        chunk.chunk_id
        for chunk in chunks
        if chunk.filename == snippet["filename"] and snippet["text"] in chunk.text
    }


def _cited_chunks(citations: list, retrieved: list) -> list:
    wanted = {citation.chunk_id for citation in citations}
    return [chunk for chunk in retrieved if chunk.chunk_id in wanted]


def _citation_pairs(answer: str, citations: list, retrieved: list) -> tuple[int, int]:
    by_id = {citation.id: citation for citation in citations}
    by_chunk = {chunk.chunk_id: chunk for chunk in retrieved}
    claims = _cited_claims(answer)
    good = 0
    total = 0
    seen: set[int] = set()
    for text, citation_ids in claims:
        for citation_id in citation_ids:
            total += 1
            seen.add(citation_id)
            citation = by_id.get(citation_id)
            if citation is None:
                continue
            chunk = by_chunk.get(citation.chunk_id)
            if chunk is None or citation.document != chunk.filename:
                continue
            if overlap_hits(text, chunk.text) < 1:
                continue
            if any(number not in chunk.text for number in numbers_in(text)):
                continue
            good += 1
    mismatched = set(by_id) ^ seen
    return good, total + len(mismatched)


def _cited_claims(answer: str) -> list[tuple[str, list[int]]]:
    matches = list(_MARKER.finditer(answer))
    claims: list[tuple[str, list[int]]] = []
    cursor = 0
    index = 0
    while index < len(matches):
        text = answer[cursor : matches[index].start()].strip()
        citation_ids = [int(matches[index].group(1))]
        end = matches[index].end()
        index += 1
        while index < len(matches) and not answer[end : matches[index].start()].strip():
            citation_ids.append(int(matches[index].group(1)))
            end = matches[index].end()
            index += 1
        if text:
            claims.append((text, citation_ids))
        cursor = end
    return claims


def _rate(numerator: int | bool, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def main() -> None:
    report = evaluate()
    METRICS.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"questions: {report['questions']}")
    print(f"handbook chunks: {report['handbook_chunks']}")
    for name in (
        "retrieval_recall",
        "citation_accuracy",
        "grounded_answer_rate",
        "unsupported_refusal_rate",
    ):
        target = report["targets"][name]
        value = report[name]
        mark = "ok" if value >= target else "MISS"
        print(f"{name}: {value:.1%}  target {target:.0%}  {mark}")
    for row in report["results"]:
        if row["reasons"]:
            print(f"  {row['id']} score={row['best_score']:.3f} {row['reasons']} :: {row['answer']}")
    print(f"wrote {METRICS}")
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
