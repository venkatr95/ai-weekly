"""Build an answer draft from retrieved passages, or from a configured language model."""

from __future__ import annotations

import json
import math
import re
from collections import Counter

from evidence_agent.citation_verification import excerpt_page
from evidence_agent.config import Settings
from evidence_agent.errors import ConfigurationError, GenerationError, ProviderError
from evidence_agent.retrieval import Retriever
from evidence_agent.schemas import (
    AnswerDraft,
    DraftCitation,
    DraftClaim,
    DraftConflict,
    DraftConflictPosition,
    DraftUnanswered,
    RetrievedPassage,
)
from evidence_agent.security import SYSTEM_PROMPT, build_user_prompt, scrub_text
from evidence_agent.textutil import (
    content_terms,
    decompose_question,
    definition_bonus,
    jaccard,
    sentence_polarity,
    shared_topic,
    split_sentences,
    tokenize,
    weighted_overlap,
)
from evidence_agent.vector_store import VectorStore

SELECTION_MARGIN = 0.12
MAX_PER_SUBQUESTION = 6


class ExtractiveGenerator:
    """Select verbatim sentences. This provider never calls a model."""

    can_retry = False
    provider_name = "extractive"

    def __init__(self, settings: Settings, store: VectorStore, retriever: Retriever) -> None:
        self.settings = settings
        self.store = store
        self.retriever = retriever

    def generate(self, question: str, passages: list[RetrievedPassage], feedback: str | None = None) -> AnswerDraft:
        del passages, feedback
        document_frequency, idf = _corpus_statistics(self.store)
        selected: list[dict] = []
        unanswered: list[DraftUnanswered] = []
        seen_sentences: set[tuple[str, str]] = set()

        for subquestion in decompose_question(question):
            terms = content_terms(subquestion)
            if len(terms) < 2:
                unanswered.append(
                    DraftUnanswered(
                        question=subquestion,
                        reason="ambiguous_wording",
                        detail="The question does not contain enough specific terms to search the documents.",
                    )
                )
                continue
            missing_tokens = _missing_tokens(subquestion, document_frequency)
            if len(missing_tokens) / len(terms) >= self.settings.missing_term_ratio:
                shown = ", ".join(missing_tokens[:8])
                unanswered.append(
                    DraftUnanswered(
                        question=subquestion,
                        reason="missing_documents",
                        detail=f"No indexed passage contains these question terms: {shown}.",
                    )
                )
                continue
            sub_passages = self.retriever.retrieve(
                subquestion,
                self.settings.retrieval_k,
                self.settings.similarity_threshold,
            )
            if not sub_passages:
                unanswered.append(
                    DraftUnanswered(
                        question=subquestion,
                        reason="insufficient_retrieval",
                        detail="No indexed passage scored above the similarity threshold for this subquestion.",
                    )
                )
                continue
            candidates = _rank_sentences(subquestion, sub_passages, self.store, idf, self.settings.support_threshold)
            if not candidates:
                unanswered.append(
                    DraftUnanswered(
                        question=subquestion,
                        reason="insufficient_evidence",
                        detail="Passages were retrieved, but no sentence overlaps this subquestion enough to support a claim.",
                    )
                )
                continue
            best_rank = candidates[0]["rank"]
            added = 0
            for candidate in candidates:
                if len(selected) >= self.settings.max_claims or added >= MAX_PER_SUBQUESTION:
                    break
                if candidate["rank"] < best_rank - SELECTION_MARGIN:
                    continue
                key = (candidate["relative_path"], candidate["normalized"])
                if key in seen_sentences:
                    continue
                seen_sentences.add(key)
                selected.append(candidate)
                added += 1

        claims = [
            DraftClaim(
                text=item["sentence"],
                evidence_status="supported",
                citations=[
                    DraftCitation(
                        chunk_id=item["chunk_id"],
                        excerpt=item["sentence"],
                        page=item["page"],
                    )
                ],
            )
            for item in selected
        ]
        conflicts = _conflicts(selected, self.settings.conflict_jaccard)
        return AnswerDraft(
            question=question,
            answer="",
            claims=claims,
            unanswered_questions=unanswered,
            conflicts=conflicts,
            abstained=not claims and not conflicts,
            limitations=[],
            provider=self.provider_name,
        )


class LanguageModelGenerator:
    """Chat-completions client for xAI or any OpenAI-compatible local server."""

    can_retry = True

    def __init__(self, settings: Settings, transport=None) -> None:
        self.settings = settings
        if settings.generation_provider == "xai":
            if not settings.xai_api_key:
                raise ConfigurationError(
                    "XAI_API_KEY is not set. Export it, or set GENERATION_PROVIDER=extractive to answer without a remote model."
                )
            self.base_url = settings.xai_base_url.rstrip("/")
            self.api_key = settings.xai_api_key
            self.model = settings.xai_model
            self.provider_name = "xai"
        elif settings.generation_provider == "openai_compatible":
            if not settings.openai_compatible_base_url or not settings.openai_compatible_model:
                raise ConfigurationError(
                    "GENERATION_PROVIDER=openai_compatible requires OPENAI_COMPATIBLE_BASE_URL and OPENAI_COMPATIBLE_MODEL."
                )
            self.base_url = settings.openai_compatible_base_url.rstrip("/")
            self.api_key = settings.openai_compatible_api_key or "local"
            self.model = settings.openai_compatible_model
            self.provider_name = "openai_compatible"
        else:
            raise ConfigurationError(f"Unsupported generation provider {settings.generation_provider!r}.")
        from evidence_agent.http_client import urllib_transport

        self.transport = transport or urllib_transport
        self.secrets = [settings.xai_api_key, settings.embedding_api_key, settings.openai_compatible_api_key]
        self.timeout = settings.request_timeout_seconds

    def generate(self, question: str, passages: list[RetrievedPassage], feedback: str | None = None) -> AnswerDraft:
        user_prompt = build_user_prompt(question, passages, feedback)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        body = self._post(payload)
        try:
            parsed = parse_model_json(_message_text(body))
            return draft_from_model_json(question, parsed, self.provider_name)
        except GenerationError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise GenerationError("The model response did not match the answer schema.") from exc

    def _post(self, payload: dict) -> dict:
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            return self.transport(url, payload, headers, self.timeout)
        except ProviderError as exc:
            message = str(exc).lower()
            if "response_format" in message:
                reduced = {key: value for key, value in payload.items() if key != "response_format"}
                try:
                    return self.transport(url, reduced, headers, self.timeout)
                except ProviderError as second:
                    raise ProviderError(scrub_text(str(second), self.secrets)) from second
            raise ProviderError(scrub_text(str(exc), self.secrets)) from exc


def parse_model_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise GenerationError("The model did not return valid JSON.") from exc
    if not isinstance(value, dict):
        raise GenerationError("The model JSON was not an object.")
    return value


def draft_from_model_json(question: str, payload: dict, provider: str) -> AnswerDraft:
    claims: list[DraftClaim] = []
    for item in payload.get("claims") or []:
        if not isinstance(item, dict):
            continue
        status = item.get("evidence_status", "supported")
        if status not in {"supported", "interpretation", "unsupported"}:
            status = "supported"
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        claims.append(DraftClaim(text=text, evidence_status=status, citations=_citations(item.get("citations"))))

    unanswered: list[DraftUnanswered] = []
    for item in payload.get("unanswered_questions") or []:
        if not isinstance(item, dict):
            continue
        reason = item.get("reason", "insufficient_evidence")
        if reason not in {
            "missing_documents",
            "insufficient_retrieval",
            "conflicting_evidence",
            "ambiguous_wording",
            "insufficient_evidence",
        }:
            reason = "insufficient_evidence"
        text = str(item.get("question") or "").strip()
        if not text:
            continue
        unanswered.append(
            DraftUnanswered(
                question=text,
                reason=reason,
                detail=str(item.get("detail") or ""),
                citations=_citations(item.get("citations")),
            )
        )

    conflicts: list[DraftConflict] = []
    for item in payload.get("conflicts") or []:
        if not isinstance(item, dict):
            continue
        positions: list[DraftConflictPosition] = []
        for position in item.get("positions") or []:
            if not isinstance(position, dict):
                continue
            summary = str(position.get("summary") or "").strip()
            if not summary:
                continue
            positions.append(DraftConflictPosition(summary=summary, citations=_citations(position.get("citations"))))
        if len(positions) < 2:
            continue
        conflicts.append(
            DraftConflict(
                topic=str(item.get("topic") or "conflicting passages"),
                positions=positions,
                resolved=False,
                note="The documents do not resolve this conflict.",
            )
        )

    abstained = bool(payload.get("abstained")) or (not claims and not conflicts)
    return AnswerDraft(
        question=question,
        answer="",
        claims=claims,
        unanswered_questions=unanswered,
        conflicts=conflicts,
        abstained=abstained,
        limitations=[],
        provider=provider,
    )


def _citations(raw) -> list[DraftCitation]:
    citations: list[DraftCitation] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        page = item.get("page")
        citations.append(
            DraftCitation(
                chunk_id=str(item.get("chunk_id") or ""),
                excerpt=str(item.get("excerpt") or ""),
                page=page if isinstance(page, int) else None,
            )
        )
    return citations


def _message_text(body: dict) -> str:
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise GenerationError("The model response did not include any choices.")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        raise GenerationError("The model response did not include a message.")
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and part.get("text"):
                parts.append(str(part["text"]))
            elif isinstance(part, str):
                parts.append(part)
        joined = "".join(parts).strip()
        if joined:
            return joined
    raise GenerationError("The model response did not include text content.")


def _corpus_statistics(store: VectorStore) -> tuple[dict[str, int], dict[str, float]]:
    frequency: Counter[str] = Counter()
    for chunk in store.chunks:
        frequency.update(content_terms(chunk.text))
    count = max(1, len(store.chunks))
    idf = {term: math.log((count + 1) / (seen + 1)) + 1.0 for term, seen in frequency.items()}
    return dict(frequency), idf


def _missing_tokens(question: str, document_frequency: dict[str, int]) -> list[str]:
    missing: list[str] = []
    seen: set[str] = set()
    question_terms = content_terms(question)
    for token in tokenize(question):
        stemmed = next(iter(content_terms(token)), None)
        if stemmed is None or stemmed not in question_terms or stemmed in seen:
            continue
        if document_frequency.get(stemmed, 0) == 0:
            seen.add(stemmed)
            missing.append(token)
    return missing


def _rank_sentences(question, passages, store: VectorStore, idf, threshold: float) -> list[dict]:
    query_terms = content_terms(question)
    chunks = store.chunks_by_id()
    ranked: list[dict] = []
    for passage in passages:
        chunk = chunks.get(passage.chunk_id)
        if chunk is None:
            continue
        for sentence in split_sentences(chunk.text):
            coverage = weighted_overlap(query_terms, content_terms(sentence), idf)
            if coverage < threshold:
                continue
            ranked.append(
                {
                    "sentence": sentence,
                    "normalized": " ".join(sentence.split()),
                    "chunk_id": chunk.chunk_id,
                    "relative_path": chunk.relative_path,
                    "page": excerpt_page(chunk, sentence),
                    "terms": content_terms(sentence),
                    "polarity": sentence_polarity(sentence),
                    "rank": coverage + definition_bonus(sentence) + (0.05 * passage.score),
                }
            )
    ranked.sort(key=lambda item: (-item["rank"], item["relative_path"], item["sentence"]))
    return ranked


def _conflicts(selected: list[dict], minimum_jaccard: float) -> list[DraftConflict]:
    conflicts: list[DraftConflict] = []
    used: set[tuple[str, str]] = set()
    for index, left in enumerate(selected):
        for right in selected[index + 1 :]:
            if left["polarity"] is None or right["polarity"] is None:
                continue
            if left["polarity"] == right["polarity"]:
                continue
            if jaccard(left["terms"], right["terms"]) < minimum_jaccard:
                continue
            key = tuple(sorted((left["normalized"], right["normalized"])))
            if key in used:
                continue
            used.add(key)
            conflicts.append(
                DraftConflict(
                    topic=shared_topic(left["terms"], right["terms"]),
                    positions=[
                        DraftConflictPosition(
                            summary=left["sentence"],
                            citations=[DraftCitation(chunk_id=left["chunk_id"], excerpt=left["sentence"], page=left["page"])],
                        ),
                        DraftConflictPosition(
                            summary=right["sentence"],
                            citations=[DraftCitation(chunk_id=right["chunk_id"], excerpt=right["sentence"], page=right["page"])],
                        ),
                    ],
                    resolved=False,
                    note="The documents do not resolve this conflict.",
                )
            )
    return conflicts
