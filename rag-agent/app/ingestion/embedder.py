"""Embedding providers.

`hashing` is a local signed feature hash. It needs no network, so tests and the
offline demo can retrieve without an API key.

`xai` calls the OpenAI-compatible embeddings endpoint on https://api.x.ai/v1.
`embed-latest` is the alias that resolves to the current embedding model
(the concrete id can be `embed-0205` when that is the latest). The vector
dimension is whatever that model returns; it is not hardcoded.
"""

import hashlib
import logging
import math
from typing import Protocol

from openai import APIError, OpenAI

from app.config import Settings
from app.errors import EmbeddingError
from app.textutil import content_terms

logger = logging.getLogger("rag_agent.embedder")

_BATCH_SIZE = 32


class Embedder(Protocol):
    name: str
    dim: int

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class HashingEmbedder:
    """Bag-of-words feature hash with unigrams, bigrams, and L2 normalization."""

    name = "hashing"

    def __init__(self, dim: int = 384) -> None:
        if dim < 32:
            raise ValueError("embedding dim must be at least 32")
        self.dim = dim

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [_embed_terms(text, self.dim) for text in texts]


class XAIEmbedder:
    """SpaceXAI embeddings via the OpenAI SDK pointed at api.x.ai."""

    name = "xai"

    def __init__(self, api_key: str, base_url: str, model: str, timeout: float) -> None:
        self.model = model
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=2)
        probe = self.embed_texts(["dimension probe"])
        self.dim = len(probe[0])
        logger.info("EMBEDDING MODEL %s dimension %d", model, self.dim)

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        try:
            for start in range(0, len(texts), _BATCH_SIZE):
                batch = texts[start : start + _BATCH_SIZE]
                response = self._client.embeddings.create(model=self.model, input=batch)
                ordered = sorted(response.data, key=lambda item: item.index)
                if len(ordered) != len(batch):
                    raise EmbeddingError("Embedding response did not contain one vector per input")
                vectors.extend(_l2_normalize(list(item.embedding)) for item in ordered)
        except EmbeddingError:
            raise
        except APIError as exc:
            raise EmbeddingError("The embedding request failed") from exc
        return vectors


def build_embedder(settings: Settings) -> Embedder:
    provider = settings.embedding_provider
    api_key = settings.resolved_api_key()
    if provider == "auto":
        provider = "xai" if api_key else "hashing"
    if provider == "hashing":
        return HashingEmbedder(settings.embedding_dim)
    if not api_key:
        raise EmbeddingError("EMBEDDING_PROVIDER=xai requires XAI_API_KEY")
    try:
        return XAIEmbedder(
            api_key=api_key,
            base_url=settings.xai_base_url,
            model=settings.embedding_model,
            timeout=settings.llm_timeout_seconds,
        )
    except EmbeddingError:
        if settings.embedding_provider == "auto":
            logger.warning(
                "xAI embeddings are unavailable; using the local hashing embedder",
                exc_info=True,
            )
            return HashingEmbedder(settings.embedding_dim)
        raise


def _embed_terms(text: str, dim: int) -> list[float]:
    terms = content_terms(text)
    if not terms:
        return [0.0] * dim
    weights: dict[str, float] = {}
    for term in terms:
        weights[term] = weights.get(term, 0.0) + 1.0
    for left, right in zip(terms, terms[1:]):
        bigram = f"{left}_{right}"
        weights[bigram] = weights.get(bigram, 0.0) + 1.0
    vector = [0.0] * dim
    for term, count in weights.items():
        digest = hashlib.md5(term.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[bucket] += sign * (1.0 + math.log(count))
    return _l2_normalize(vector)


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]
