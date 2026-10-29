"""Embedding providers. The default provider is local and does not call the network."""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from typing import Protocol

import numpy as np

from evidence_agent.config import Settings
from evidence_agent.errors import ConfigurationError, ProviderError
from evidence_agent.security import scrub_text
from evidence_agent.textutil import feature_grams

LOCAL_STATE_VERSION = "local-hash-tfidf-v1"


class Embedder(Protocol):
    dimensions: int
    provider_name: str
    reuses_vectors: bool

    def fit(self, texts: list[str]) -> None: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...

    def state_dict(self) -> dict: ...

    def load_state(self, state: dict) -> None: ...


def _bucket_and_sign(feature: str, dimensions: int) -> tuple[int, float]:
    digest = hashlib.sha256(feature.encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:4], "little") % dimensions
    sign = 1.0 if digest[4] % 2 == 0 else -1.0
    return bucket, sign


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


class LocalHashingEmbedder:
    """Hashed TF-IDF vectors. Deterministic, offline, and not a semantic model.

    Unseen query features are ignored so out-of-corpus words do not land in a
    random bucket and retrieve an unrelated passage.
    """

    provider_name = "local"
    reuses_vectors = False

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions
        self.idf: dict[str, float] = {}
        self.unigram_df: dict[str, int] = {}
        self.chunk_count = 0

    def fit(self, texts: list[str]) -> None:
        document_frequency: Counter[str] = Counter()
        unigram_df: Counter[str] = Counter()
        for text in texts:
            grams = feature_grams(text)
            document_frequency.update(set(grams))
            unigrams = {gram for gram in grams if "_" not in gram}
            unigram_df.update(unigrams)
        count = max(1, len(texts))
        self.chunk_count = len(texts)
        self.unigram_df = dict(unigram_df)
        self.idf = {
            feature: math.log((count + 1) / (frequency + 1)) + 1.0
            for feature, frequency in document_frequency.items()
        }

    def _vectorize(self, texts: list[str], skip_unseen: bool) -> list[list[float]]:
        if not texts:
            return []
        matrix = np.zeros((len(texts), self.dimensions), dtype=np.float32)
        for row, text in enumerate(texts):
            counts = Counter(feature_grams(text))
            for feature, count in counts.items():
                if skip_unseen and feature not in self.idf:
                    continue
                weight = (1.0 + math.log(count)) * self.idf.get(feature, 1.0)
                bucket, sign = _bucket_and_sign(feature, self.dimensions)
                matrix[row, bucket] += sign * weight
        matrix = _l2_normalize(matrix)
        return matrix.tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._vectorize(texts, skip_unseen=False)

    def embed_query(self, text: str) -> list[float]:
        vectors = self._vectorize([text], skip_unseen=True)
        if not vectors:
            return [0.0] * self.dimensions
        return vectors[0]

    def state_dict(self) -> dict:
        return {
            "version": LOCAL_STATE_VERSION,
            "dimensions": self.dimensions,
            "idf": self.idf,
            "unigram_df": self.unigram_df,
            "chunk_count": self.chunk_count,
        }

    def load_state(self, state: dict) -> None:
        if state.get("version") != LOCAL_STATE_VERSION:
            raise ConfigurationError(
                "The index uses an unsupported local embedding state. Rebuild it with --rebuild."
            )
        dimensions = int(state.get("dimensions", 0))
        if dimensions != self.dimensions:
            raise ConfigurationError(
                f"The index was built with {dimensions} embedding dimensions, "
                f"but EMBEDDING_DIMENSIONS is {self.dimensions}. Rebuild the index or restore the original value."
            )
        self.idf = {str(key): float(value) for key, value in state.get("idf", {}).items()}
        self.unigram_df = {str(key): int(value) for key, value in state.get("unigram_df", {}).items()}
        self.chunk_count = int(state.get("chunk_count", 0))


class HttpEmbedder:
    """OpenAI-compatible POST /embeddings client. Not used by the offline default."""

    provider_name = "http"
    reuses_vectors = True

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        dimensions: int,
        timeout: float,
        transport,
        secrets: list[str | None],
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self.timeout = timeout
        self.transport = transport
        self.secrets = secrets

    def fit(self, texts: list[str]) -> None:
        return None

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        url = f"{self.base_url}/embeddings"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        vectors: list[list[float]] = []
        batch_size = 32
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            payload = {"model": self.model, "input": batch}
            try:
                body = self.transport(url, payload, headers, self.timeout)
            except ProviderError:
                raise
            except Exception as exc:
                raise ProviderError(
                    "The embedding request failed. Check EMBEDDING_BASE_URL, EMBEDDING_MODEL, and EMBEDDING_API_KEY. "
                    + scrub_text(str(exc), self.secrets)
                ) from exc
            data = body.get("data") if isinstance(body, dict) else None
            if not isinstance(data, list) or len(data) != len(batch):
                raise ProviderError(
                    "The embedding provider returned an unexpected response. Expected one vector per input text."
                )
            ordered = sorted(data, key=lambda item: item.get("index", 0))
            for item in ordered:
                embedding = item.get("embedding")
                if not isinstance(embedding, list) or len(embedding) != self.dimensions:
                    raise ProviderError(
                        "The embedding provider returned a vector with the wrong length. "
                        f"Expected {self.dimensions}. Set EMBEDDING_DIMENSIONS to the model size and rebuild the index."
                    )
                vectors.append([float(value) for value in embedding])
        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        vectors = self._embed([text])
        return vectors[0]

    def state_dict(self) -> dict:
        return {
            "version": "http-embeddings-v1",
            "dimensions": self.dimensions,
            "model": self.model,
            "base_url": self.base_url,
        }

    def load_state(self, state: dict) -> None:
        if state.get("version") != "http-embeddings-v1":
            raise ConfigurationError("The index embedding state does not match the HTTP provider. Rebuild with --rebuild.")
        if int(state.get("dimensions", 0)) != self.dimensions or state.get("model") != self.model:
            raise ConfigurationError(
                "The index was built with a different HTTP embedding model or dimension. Rebuild the index."
            )


def build_embedder(settings: Settings, transport=None) -> Embedder:
    if settings.embedding_provider == "local":
        return LocalHashingEmbedder(settings.embedding_dimensions)
    if not settings.embedding_base_url or not settings.embedding_api_key or not settings.embedding_model:
        raise ConfigurationError(
            "EMBEDDING_PROVIDER=http requires EMBEDDING_BASE_URL, EMBEDDING_API_KEY, and EMBEDDING_MODEL. "
            "Leave EMBEDDING_PROVIDER=local to index without a network call."
        )
    from evidence_agent.http_client import urllib_transport

    return HttpEmbedder(
        base_url=settings.embedding_base_url,
        api_key=settings.embedding_api_key,
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
        timeout=settings.request_timeout_seconds,
        transport=transport or urllib_transport,
        secrets=[settings.embedding_api_key, settings.xai_api_key, settings.openai_compatible_api_key],
    )
