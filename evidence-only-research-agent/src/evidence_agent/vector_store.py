"""Persistent local index. Chunk text is stored so citations can be checked."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from evidence_agent.errors import CorruptIndexError, IndexNotFoundError
from evidence_agent.schemas import Chunk, DocumentRecord

INDEX_VERSION = 1
MANIFEST_NAME = "manifest.json"
EMBEDDINGS_NAME = "embeddings.npy"


class VectorStore:
    def __init__(self, index_dir: Path) -> None:
        self.index_dir = index_dir
        self.documents: list[DocumentRecord] = []
        self.chunks: list[Chunk] = []
        self.embeddings: np.ndarray | None = None
        self.embedder_state: dict = {}
        self.manifest: dict = {}

    @property
    def manifest_path(self) -> Path:
        return self.index_dir / MANIFEST_NAME

    @property
    def embeddings_path(self) -> Path:
        return self.index_dir / EMBEDDINGS_NAME

    def exists(self) -> bool:
        return self.manifest_path.is_file() and self.embeddings_path.is_file()

    def chunks_by_id(self) -> dict[str, Chunk]:
        return {chunk.chunk_id: chunk for chunk in self.chunks}

    def vector_by_id(self) -> dict[str, list[float]]:
        if self.embeddings is None:
            return {}
        mapping: dict[str, list[float]] = {}
        for chunk, vector in zip(self.chunks, self.embeddings.tolist()):
            mapping[chunk.chunk_id] = vector
        return mapping

    def load(self) -> None:
        if not self.exists():
            raise IndexNotFoundError(
                f"No index at {self.index_dir}. Run: python cli.py index <documents-folder>"
            )
        try:
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            embeddings = np.load(self.embeddings_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise CorruptIndexError(
                f"The index at {self.index_dir} is unreadable. Run index again with --rebuild. ({exc.__class__.__name__})"
            ) from exc
        if not isinstance(manifest, dict) or manifest.get("version") != INDEX_VERSION:
            raise CorruptIndexError(
                f"The index at {self.index_dir} is incompatible. Run index again with --rebuild."
            )
        try:
            documents = [DocumentRecord.model_validate(item) for item in manifest["documents"]]
            chunks = [Chunk.model_validate(item) for item in manifest["chunks"]]
        except (KeyError, ValueError) as exc:
            raise CorruptIndexError(
                f"The index at {self.index_dir} is missing document data. Run index again with --rebuild."
            ) from exc
        if embeddings.ndim != 2 or embeddings.shape[0] != len(chunks):
            raise CorruptIndexError(
                f"The index at {self.index_dir} has embeddings that do not match its chunks. Run index again with --rebuild."
            )
        self.manifest = manifest
        self.documents = documents
        self.chunks = chunks
        self.embeddings = embeddings.astype(np.float32)
        self.embedder_state = manifest.get("embedder_state") or {}

    def save(
        self,
        *,
        documents: list[DocumentRecord],
        chunks: list[Chunk],
        embeddings: np.ndarray,
        embedder_state: dict,
        embedding_provider: str,
        embedding_dimensions: int,
        chunk_size: int,
        chunk_overlap: int,
        stats: dict,
        errors: list[str],
        ocr_warnings: list[str],
    ) -> None:
        if embeddings.ndim != 2:
            raise CorruptIndexError("Refusing to save an index with malformed embeddings.")
        if embeddings.shape[0] != len(chunks):
            raise CorruptIndexError("Refusing to save an index whose embeddings do not match its chunks.")
        if len(chunks) and embeddings.shape[1] != embedding_dimensions:
            raise CorruptIndexError(
                "Refusing to save embeddings whose width does not match EMBEDDING_DIMENSIONS."
            )
        self.index_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "version": INDEX_VERSION,
            "embedding_provider": embedding_provider,
            "embedding_dimensions": embedding_dimensions,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "documents": [document.model_dump() for document in documents],
            "chunks": [chunk.model_dump() for chunk in chunks],
            "embedder_state": embedder_state,
            "stats": stats,
            "errors": errors,
            "ocr_warnings": ocr_warnings,
        }
        _atomic_text(self.manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2))
        _atomic_npy(self.embeddings_path, embeddings.astype(np.float32))
        self.manifest = manifest
        self.documents = documents
        self.chunks = chunks
        self.embeddings = embeddings.astype(np.float32)
        self.embedder_state = embedder_state


def _atomic_text(path: Path, text: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _atomic_npy(path: Path, embeddings: np.ndarray) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.save(handle, embeddings)
    temporary.replace(path)
