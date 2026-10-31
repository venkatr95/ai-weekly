"""Find source sentences that are relevant to a claim.

Retrieval only selects passages. It does not decide whether a claim is true.
A low score means the passage was not retrieved, not that the claim is false.
"""

from __future__ import annotations

from answer_auditor.claim_verifier import detect_metrics
from answer_auditor.schemas import Passage, SourceDocument
from answer_auditor.sentence_segmenter import split_paragraphs, split_sentences
from answer_auditor.textutil import term_coverage


class SourcedSentence:
    def __init__(
        self,
        source_id: str,
        source_title: str | None,
        page: int | None,
        text: str,
        context: str,
    ) -> None:
        self.source_id = source_id
        self.source_title = source_title
        self.page = page
        self.text = text
        self.context = context


def iter_sentences(documents: list[SourceDocument]) -> list[SourcedSentence]:
    sentences: list[SourcedSentence] = []
    for document in documents:
        for page in document.pages:
            paragraphs = split_paragraphs(page.text)
            for paragraph in paragraphs:
                parts = split_sentences(paragraph)
                for index, sentence in enumerate(parts):
                    cleaned = sentence.strip()
                    if len(cleaned) < 8:
                        continue
                    previous_text = parts[index - 1].strip() if index else ""
                    next_text = parts[index + 1].strip() if index + 1 < len(parts) else ""
                    context = " ".join(part for part in (previous_text, cleaned, next_text) if part)
                    sentences.append(
                        SourcedSentence(
                            source_id=document.source_id,
                            source_title=document.title,
                            page=page.page_number,
                            text=cleaned,
                            context=context,
                        )
                    )
    return sentences


def retrieve_evidence(
    claim_text: str,
    documents: list[SourceDocument],
    k: int = 6,
) -> list[Passage]:
    claim_metrics = detect_metrics(claim_text)
    ranked: list[tuple[float, SourcedSentence]] = []
    for sentence in iter_sentences(documents):
        lexical = term_coverage(claim_text, sentence.text)
        sentence_metrics = detect_metrics(sentence.text)
        metric_overlap = bool(claim_metrics and sentence_metrics and (claim_metrics & sentence_metrics))
        score = min(1.0, lexical * 0.5 + (0.55 if metric_overlap else 0.0))
        include = metric_overlap or lexical >= 0.45 or score >= 0.5
        if include:
            ranked.append((score, sentence))
    ranked.sort(key=lambda item: item[0], reverse=True)
    passages: list[Passage] = []
    for score, sentence in ranked[:k]:
        passages.append(
            Passage(
                source_id=sentence.source_id,
                source_title=sentence.source_title,
                page=sentence.page,
                text=sentence.text,
                context=sentence.context,
                score=round(score, 4),
            )
        )
    return passages
