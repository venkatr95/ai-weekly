"""Runtime settings. Credentials come from the environment, never from source files."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

from answer_auditor.errors import ConfigurationError


def load_dotenv(path: Path | None = None) -> None:
    """Load a local .env file without overriding variables that are already set."""

    env_path = path or Path.cwd() / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def _flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Settings(BaseModel):
    provider: str = "heuristic"
    xai_api_key: str | None = None
    xai_model: str = "grok-4.7"
    xai_base_url: str = "https://api.x.ai/v1"
    request_timeout_seconds: float = 60.0
    retrieval_k: int = 6
    log_source_text: bool = False
    secrets: list[str] = Field(default_factory=list)

    def require_xai(self) -> None:
        if not self.xai_api_key:
            raise ConfigurationError(
                "AUDITOR_PROVIDER=xai requires XAI_API_KEY. "
                "The key is read from the environment and is not stored in reports."
            )


def load_settings(provider: str | None = None) -> Settings:
    load_dotenv()
    selected = (provider or os.environ.get("AUDITOR_PROVIDER") or "heuristic").strip().lower()
    if selected not in {"heuristic", "xai"}:
        raise ConfigurationError(
            f"Unknown provider '{selected}'. Use 'heuristic' or 'xai'."
        )
    api_key = os.environ.get("XAI_API_KEY") or None
    if api_key is not None:
        api_key = api_key.strip() or None
    settings = Settings(
        provider=selected,
        xai_api_key=api_key,
        xai_model=os.environ.get("XAI_MODEL", "grok-4.7").strip() or "grok-4.7",
        xai_base_url=os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1").strip().rstrip("/")
        or "https://api.x.ai/v1",
        log_source_text=_flag("AUDITOR_LOG_SOURCES", False),
        secrets=[api_key] if api_key else [],
    )
    if settings.provider == "xai":
        settings.require_xai()
    return settings
