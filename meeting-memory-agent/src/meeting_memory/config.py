"""Runtime configuration. The default path never calls a network service."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from meeting_memory.errors import ConfigurationError

TranscriberName = Literal["sidecar", "whisper"]


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


class Settings(BaseModel):
    index_dir: Path = Field(default=Path("data/index"))
    transcriber: TranscriberName = "sidecar"
    whisper_model: str = "base"
    max_text_bytes: int = 2_000_000
    max_audio_bytes: int = 200_000_000
    retention_days: int | None = None

    @model_validator(mode="after")
    def check_bounds(self) -> "Settings":
        if self.max_text_bytes < 1:
            raise ConfigurationError("max_text_bytes must be at least 1.")
        if self.max_audio_bytes < 1:
            raise ConfigurationError("max_audio_bytes must be at least 1.")
        if self.retention_days is not None and self.retention_days < 0:
            raise ConfigurationError("retention_days must be zero or greater.")
        if not self.whisper_model.strip():
            raise ConfigurationError("whisper_model must not be empty.")
        return self

    @classmethod
    def from_env(cls, index_dir: Path | None = None, env_file: Path | None = None) -> "Settings":
        load_dotenv(env_file or Path(".env"))
        transcriber = _env_str("MEETING_TRANSCRIBER", "sidecar")
        if transcriber not in {"sidecar", "whisper"}:
            raise ConfigurationError(
                "MEETING_TRANSCRIBER must be sidecar or whisper. "
                f"Received {transcriber!r}."
            )
        retention_raw = _env_str("MEETING_RETENTION_DAYS")
        if retention_raw is None:
            retention_days = None
        else:
            try:
                retention_days = int(retention_raw)
            except ValueError as exc:
                raise ConfigurationError(
                    f"MEETING_RETENTION_DAYS must be an integer. Received {retention_raw!r}."
                ) from exc
        settings = cls(
            index_dir=index_dir or Path(_env_str("MEETING_INDEX_DIR", "data/index") or "data/index"),
            transcriber=transcriber,  # type: ignore[arg-type]
            whisper_model=_env_str("MEETING_WHISPER_MODEL", "base") or "base",
            max_text_bytes=_env_int("MEETING_MAX_TEXT_BYTES", 2_000_000),
            max_audio_bytes=_env_int("MEETING_MAX_AUDIO_BYTES", 200_000_000),
            retention_days=retention_days,
        )
        return settings
