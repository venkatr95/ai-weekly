from __future__ import annotations

from pathlib import Path

from evidence_agent.config import Settings
from evidence_agent.pipeline import ResearchPipeline


def build_settings(tmp_path: Path, **overrides) -> Settings:
    values = {
        "index_dir": tmp_path / "index",
        "chunk_size": 120,
        "chunk_overlap": 20,
        "retrieval_k": 6,
        "similarity_threshold": 0.12,
        "generation_provider": "extractive",
        "embedding_provider": "local",
        "embedding_dimensions": 384,
    }
    values.update(overrides)
    return Settings(**values)


def write_corpus(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def indexed_pipeline(tmp_path: Path, files: dict[str, str], **overrides) -> ResearchPipeline:
    root = write_corpus(tmp_path / "docs", files)
    pipeline = ResearchPipeline(build_settings(tmp_path, **overrides))
    pipeline.index_path(root, rebuild=True)
    return pipeline
