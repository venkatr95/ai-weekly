"""Runtime settings. Version 1 does not call a model."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Settings(BaseModel):
    max_chars: int = Field(default=1_000_000, ge=1)
    provider: Literal["heuristic"] = "heuristic"
