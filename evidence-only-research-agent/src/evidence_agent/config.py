"""Runtime configuration. Secrets are read from the environment, never from code."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from evidence_agent.errors import ConfigurationError

GenerationProvider = Literal["extractive", "xai", "openai_compatible"]
EmbeddingProvider = Literal["local", "http"]


def load_dotenv(path: Path) -> None:
    """Load KEY=VALUE pairs that are not already set in the environment."""

    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _env_str(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _env_int(name: str, default: int) -> int:
    raw = _env_str(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer. Received {raw!r}.") from exc


def _env_float(name: str, default: float) -> float:
    raw = _env_str(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a number. Received {raw!r}.") from exc


def _env_bool(name: str, default: bool) -> bool:
    raw = _env_str(name)
    if raw is None:
        return default
    normalized = raw.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be true or false. Received {raw!r}.")


class Settings(BaseModel):
    index_dir: Path = Field(default=Path("data/index"))
    chunk_size: int = 800
    chunk_overlap: int = 120
    retrieval_k: int = 6
    similarity_threshold: float = 0.15
    support_threshold: float = 0.55
    missing_term_ratio: float = 0.4
    conflict_jaccard: float = 0.28
    max_claims: int = 8
    embedding_provider: EmbeddingProvider = "local"
    embedding_dimensions: int = 384
    embedding_base_url: str | None = None
    embedding_api_key: str | None = None
    embedding_model: str | None = None
    generation_provider: GenerationProvider = "extractive"
    xai_api_key: str | None = None
    xai_model: str = "grok-4.7"
    xai_base_url: str = "https://api.x.ai/v1"
    openai_compatible_base_url: str | None = None
    openai_compatible_api_key: str | None = None
    openai_compatible_model: str | None = None
    log_document_text: bool = False
    request_timeout_seconds: float = 60.0

    @model_validator(mode="after")
    def check_ranges(self) -> Settings:
        if self.chunk_size < 20:
            raise ValueError("CHUNK_SIZE must be at least 20 whitespace tokens.")
        if self.chunk_overlap < 0 or self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be zero or greater and smaller than CHUNK_SIZE.")
        if self.retrieval_k < 1:
            raise ValueError("RETRIEVAL_K must be at least 1.")
        if not 0 <= self.similarity_threshold <= 1:
            raise ValueError("SIMILARITY_THRESHOLD must be between 0 and 1.")
        if not 0 < self.support_threshold <= 1:
            raise ValueError("SUPPORT_THRESHOLD must be greater than 0 and at most 1.")
        if self.embedding_dimensions < 32:
            raise ValueError("EMBEDDING_DIMENSIONS must be at least 32.")
        if self.max_claims < 1:
            raise ValueError("max_claims must be at least 1.")
        return self

    @classmethod
    def load(cls, env_file: Path | None = None) -> Settings:
        if env_file is None:
            env_file = Path.cwd() / ".env"
        load_dotenv(env_file)
        provider = _env_str("GENERATION_PROVIDER", "extractive")
        embedding = _env_str("EMBEDDING_PROVIDER", "local")
        if provider not in {"extractive", "xai", "openai_compatible"}:
            raise ConfigurationError(
                "GENERATION_PROVIDER must be extractive, xai, or openai_compatible. "
                f"Received {provider!r}."
            )
        if embedding not in {"local", "http"}:
            raise ConfigurationError(
                "EMBEDDING_PROVIDER must be local or http. "
                f"Received {embedding!r}."
            )
        try:
            return cls(
                index_dir=Path(_env_str("INDEX_DIR", "data/index") or "data/index"),
                chunk_size=_env_int("CHUNK_SIZE", 800),
                chunk_overlap=_env_int("CHUNK_OVERLAP", 120),
                retrieval_k=_env_int("RETRIEVAL_K", 6),
                similarity_threshold=_env_float("SIMILARITY_THRESHOLD", 0.15),
                support_threshold=_env_float("SUPPORT_THRESHOLD", 0.55),
                embedding_provider=embedding,  # type: ignore[arg-type]
                embedding_dimensions=_env_int("EMBEDDING_DIMENSIONS", 384),
                embedding_base_url=_env_str("EMBEDDING_BASE_URL"),
                embedding_api_key=_env_str("EMBEDDING_API_KEY"),
                embedding_model=_env_str("EMBEDDING_MODEL"),
                generation_provider=provider,  # type: ignore[arg-type]
                xai_api_key=_env_str("XAI_API_KEY"),
                xai_model=_env_str("XAI_MODEL", "grok-4.7") or "grok-4.7",
                xai_base_url=_env_str("XAI_BASE_URL", "https://api.x.ai/v1") or "https://api.x.ai/v1",
                openai_compatible_base_url=_env_str("OPENAI_COMPATIBLE_BASE_URL"),
                openai_compatible_api_key=_env_str("OPENAI_COMPATIBLE_API_KEY"),
                openai_compatible_model=_env_str("OPENAI_COMPATIBLE_MODEL"),
                log_document_text=_env_bool("LOG_DOCUMENT_TEXT", False),
                request_timeout_seconds=_env_float("REQUEST_TIMEOUT_SECONDS", 60.0),
            )
        except ValueError as exc:
            raise ConfigurationError(str(exc)) from exc

    def scrubbed(self, message: str) -> str:
        secrets = [
            self.xai_api_key,
            self.embedding_api_key,
            self.openai_compatible_api_key,
        ]
        redacted = message
        for secret in secrets:
            if secret and len(secret) >= 6:
                redacted = redacted.replace(secret, "[redacted]")
        return redacted
