"""Runtime configuration.

Environment variables override the defaults. `make_settings` ignores the
environment so tests and the evaluation run are hermetic.
"""

from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://rag:rag@localhost:5432/rag"
    vector_store: Literal["postgres", "memory"] = "postgres"

    xai_api_key: str | None = None
    xai_base_url: str = "https://api.x.ai/v1"
    llm_model: str = "grok-4.7"
    llm_provider: Literal["auto", "xai", "extractive"] = "auto"
    llm_timeout_seconds: float = 120
    # grok-4.7 reasoning cannot be disabled. Low effort fits grounded extraction.
    reasoning_effort: Literal["low", "medium", "high", "xhigh"] = "low"

    embedding_provider: Literal["auto", "xai", "hashing"] = "auto"
    embedding_model: str = "embed-latest"
    embedding_dim: int = Field(default=384, ge=32, le=8192)

    chunk_size_tokens: int = Field(default=500, ge=20, le=4000)
    chunk_overlap_tokens: int = Field(default=100, ge=0, le=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    # None selects a provider-specific default in the pipeline.
    min_score: float | None = None
    vector_weight: float | None = None
    rerank_pool_multiplier: int = Field(default=6, ge=1, le=20)

    max_upload_bytes: int = Field(default=20 * 1024 * 1024, ge=1)
    log_level: str = "INFO"

    @model_validator(mode="after")
    def overlap_fits_in_chunk(self) -> "Settings":
        if self.chunk_overlap_tokens >= self.chunk_size_tokens:
            raise ValueError("CHUNK_OVERLAP_TOKENS must be smaller than CHUNK_SIZE_TOKENS")
        if self.min_score is not None and not 0 <= self.min_score <= 1:
            raise ValueError("MIN_SCORE must be between 0 and 1")
        if self.vector_weight is not None and not 0 <= self.vector_weight <= 1:
            raise ValueError("VECTOR_WEIGHT must be between 0 and 1")
        return self

    def resolved_api_key(self) -> str | None:
        key = (self.xai_api_key or "").strip()
        return key or None


@lru_cache
def get_settings() -> Settings:
    return Settings()


def make_settings(**overrides: Any) -> Settings:
    """Settings from explicit values only, ignoring environment variables and `.env`."""
    return Settings.model_validate(overrides)
