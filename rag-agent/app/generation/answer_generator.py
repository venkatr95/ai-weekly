"""Turn retrieved chunks into claims.

The xAI generator calls grok-4.7 through the OpenAI SDK
(`base_url=https://api.x.ai/v1`) and requires a structured object. The
extractive generator is the offline fallback: it quotes sentences from the
retrieved chunks and never calls a model. Both outputs still pass through
citation validation, which drops anything the chunks do not support.
"""

import logging
import re
from typing import Protocol

from openai import APIError, OpenAI

from app.config import Settings
from app.errors import GenerationError
from app.schemas.answer import Claim, ModelAnswer, RetrievedChunk
from app.textutil import content_terms, min_hits_required, overlap_hits, significant_terms, term_matches

logger = logging.getLogger("rag_agent.generation")

_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")

SYSTEM_PROMPT = """You are a document question-answering system.

Answer the user's question using only the supplied sources.

Rules:
1. Do not use outside knowledge.
2. Do not invent facts.
3. Every factual claim must have a citation.
4. If the sources do not contain enough information, say so.
5. Cite the source number immediately after the relevant claim.

Output rules:
- Set sufficient to false and return an empty claims list when the sources do not contain enough information to answer.
- When sufficient is true, split the answer into separate claims. Each claim is one factual sentence.
- Do not put citation markers such as [1] inside the claim text. Put the SOURCE numbers in citation_ids.
- Every claim must be supported by the cited sources. Keep numbers, durations, and policy names as they appear in the sources.
- citation_ids must refer only to SOURCE numbers present in the context.
"""


class AnswerGenerator(Protocol):
    name: str

    def generate(self, question: str, sources: list[RetrievedChunk]) -> ModelAnswer: ...


def assemble_context(sources: list[RetrievedChunk]) -> str:
    blocks: list[str] = []
    for index, source in enumerate(sources, start=1):
        page = "n/a" if source.page is None else str(source.page)
        blocks.append(
            f"SOURCE [{index}]\nDocument: {source.filename}\nPage: {page}\n\n{source.text}"
        )
    return "\n\n".join(blocks)


class ExtractiveGenerator:
    """Quote the best supporting sentence from each strong chunk."""

    name = "extractive"

    def generate(self, question: str, sources: list[RetrievedChunk]) -> ModelAnswer:
        if not sources:
            return ModelAnswer(sufficient=False, claims=[])
        required = min_hits_required(question)
        scored: list[tuple[int, int, str]] = []
        for index, source in enumerate(sources, start=1):
            best: tuple[int, str] | None = None
            for sentence in _sentences(source.text):
                hits = overlap_hits(question, sentence)
                if hits < required:
                    continue
                if best is None or hits > best[0]:
                    best = (hits, sentence)
            if best is not None:
                scored.append((best[0], index, best[1]))
        if not scored:
            return ModelAnswer(sufficient=False, claims=[])
        # Drop a sentence whose matched question-terms are already covered by
        # a more specific sentence. A weeks question then does not also cite
        # the approval sentence, while a question that needs both still keeps both.
        covered = [
            (hits, index, sentence, _matched_query_terms(question, sentence))
            for hits, index, sentence in scored
        ]
        specific = [
            item
            for item in covered
            if not any(item[3] < other[3] for other in covered)
        ]
        specific.sort(key=lambda item: (-item[0], item[1]))
        claims: list[Claim] = []
        seen: set[str] = set()
        for _, index, sentence, _matched in specific:
            key = sentence.casefold()
            if key in seen:
                continue
            seen.add(key)
            claims.append(Claim(text=sentence, citation_ids=[index]))
            if len(claims) == 4:
                break
        return ModelAnswer(sufficient=True, claims=claims)


class XAIGenerator:
    """grok-4.7 structured output. No web search and no tools, so it cannot leave the sources."""

    def __init__(self, api_key: str, base_url: str, model: str, timeout: float, reasoning_effort: str) -> None:
        self.name = f"xai:{model}"
        self.model = model
        self.reasoning_effort = reasoning_effort
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=2)

    def generate(self, question: str, sources: list[RetrievedChunk]) -> ModelAnswer:
        if not sources:
            return ModelAnswer(sufficient=False, claims=[])
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Sources:\n{assemble_context(sources)}\n\nQuestion:\n{question}",
            },
        ]
        try:
            completion = self._client.beta.chat.completions.parse(
                model=self.model,
                messages=messages,
                response_format=ModelAnswer,
                extra_body={"reasoning_effort": self.reasoning_effort},
            )
        except APIError as exc:
            logger.exception("LLM request failed")
            raise GenerationError("The language model request failed") from exc
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise GenerationError("The language model returned an empty answer")
        return parsed


def build_generator(settings: Settings) -> AnswerGenerator:
    provider = settings.llm_provider
    api_key = settings.resolved_api_key()
    if provider == "auto":
        provider = "xai" if api_key else "extractive"
    if provider == "extractive":
        return ExtractiveGenerator()
    if not api_key:
        raise GenerationError("LLM_PROVIDER=xai requires XAI_API_KEY")
    return XAIGenerator(
        api_key=api_key,
        base_url=settings.xai_base_url,
        model=settings.llm_model,
        timeout=settings.llm_timeout_seconds,
        reasoning_effort=settings.reasoning_effort,
    )


def _matched_query_terms(query: str, sentence: str) -> frozenset[str]:
    found = set(content_terms(sentence))
    return frozenset(term for term in significant_terms(query) if term_matches(term, found))


def _sentences(text: str) -> list[str]:
    sentences: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for part in _SENTENCE_BREAK.split(stripped):
            sentence = part.strip()
            if len(sentence) >= 20:
                sentences.append(sentence)
    return sentences
