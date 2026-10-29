"""Index documents and answer questions from the local index."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from evidence_agent.answer_generation import ExtractiveGenerator, LanguageModelGenerator
from evidence_agent.chunking import chunk_document, document_id_for
from evidence_agent.citation_verification import verify_answer
from evidence_agent.config import Settings
from evidence_agent.embeddings import Embedder, build_embedder
from evidence_agent.errors import ConfigurationError, EmptyCorpusError, GenerationError
from evidence_agent.ingestion import discover_files, extract_file, hash_file
from evidence_agent.retrieval import Retriever
from evidence_agent.schemas import (
    AnswerResponse,
    Chunk,
    DocumentRecord,
    IndexReport,
    IndexStats,
    RetrievedPassage,
)
from evidence_agent.vector_store import VectorStore

logger = logging.getLogger("evidence_agent.pipeline")


class ResearchPipeline:
    def __init__(self, settings: Settings, embedder: Embedder | None = None, generator=None, transport=None) -> None:
        self.settings = settings
        self.store = VectorStore(settings.index_dir)
        self.embedder = embedder or build_embedder(settings, transport=transport)
        self.retriever = Retriever(self.store, self.embedder)
        self._generator = generator
        self.transport = transport

    def index_path(self, source: Path, rebuild: bool = False) -> IndexReport:
        supported, skipped = discover_files(source)
        if not supported:
            raise EmptyCorpusError(
                f"No supported documents in {source}. Supported types: .pdf, .txt, .md, .markdown."
            )
        previous: VectorStore | None = None
        if self.store.exists() and not rebuild:
            self.store.load()
            previous = self.store
        old_documents = {document.relative_path: document for document in previous.documents} if previous else {}
        old_chunks = previous.chunks_by_id() if previous else {}
        params_match = bool(
            previous
            and previous.manifest.get("chunk_size") == self.settings.chunk_size
            and previous.manifest.get("chunk_overlap") == self.settings.chunk_overlap
        )

        documents: list[DocumentRecord] = []
        chunks: list[Chunk] = []
        errors: list[str] = []
        ocr_warnings: list[str] = []
        reused = 0
        failed = 0
        empty = 0
        needs_ocr = 0

        for item in supported:
            path = Path(item.absolute_path)
            old = old_documents.get(item.relative_path)
            try:
                digest = hash_file(path)
            except OSError as exc:
                failed += 1
                message = f"Could not read file ({exc.__class__.__name__})."
                errors.append(f"{item.relative_path}: {message}")
                documents.append(
                    DocumentRecord(
                        document_id=document_id_for(item.relative_path),
                        relative_path=item.relative_path,
                        file_type=item.file_type,
                        content_hash="",
                        error=message,
                    )
                )
                continue
            if old and params_match and old.content_hash == digest and not old.error:
                documents.append(old)
                chunks.extend(old_chunks[chunk_id] for chunk_id in old.chunk_ids if chunk_id in old_chunks)
                reused += 1
                if old.needs_ocr:
                    needs_ocr += 1
                    if old.warning:
                        ocr_warnings.append(f"{old.relative_path}: {old.warning}")
                continue

            extracted = extract_file(path, item.relative_path)
            doc_chunks = chunk_document(extracted, self.settings.chunk_size, self.settings.chunk_overlap)
            char_count = sum(len(page.text) for page in extracted.pages)
            record = DocumentRecord(
                document_id=document_id_for(extracted.relative_path),
                relative_path=extracted.relative_path,
                file_type=extracted.file_type,
                content_hash=extracted.content_hash,
                page_count=len(extracted.pages) if extracted.file_type == "pdf" else None,
                needs_ocr=extracted.needs_ocr,
                ocr_pages=extracted.ocr_pages,
                error=extracted.error,
                warning=extracted.warning,
                chunk_ids=[chunk.chunk_id for chunk in doc_chunks],
                char_count=char_count,
            )
            if extracted.error:
                failed += 1
                errors.append(f"{item.relative_path}: {extracted.error}")
            elif char_count == 0 and not extracted.needs_ocr:
                empty += 1
            if extracted.needs_ocr:
                needs_ocr += 1
                if extracted.warning:
                    ocr_warnings.append(f"{item.relative_path}: {extracted.warning}")
            documents.append(record)
            chunks.extend(doc_chunks)
            logger.info("indexed %s chunks=%s ocr=%s", item.relative_path, len(doc_chunks), extracted.needs_ocr)

        texts = [chunk.text for chunk in chunks]
        self.embedder.fit(texts)
        vectors = self._embed_chunks(chunks, previous)
        matrix = (
            np.asarray(vectors, dtype=np.float32)
            if vectors
            else np.zeros((0, self.embedder.dimensions), dtype=np.float32)
        )
        indexed = sum(1 for document in documents if not document.error)
        stats = IndexStats(
            files_seen=len(supported) + len(skipped),
            files_indexed=indexed,
            files_reused=reused,
            files_skipped=len(skipped),
            files_failed=failed,
            files_empty=empty,
            files_needs_ocr=needs_ocr,
            documents=len(documents),
            chunks=len(chunks),
        )
        self.store.save(
            documents=documents,
            chunks=chunks,
            embeddings=matrix,
            embedder_state=self.embedder.state_dict(),
            embedding_provider=self.embedder.provider_name,
            embedding_dimensions=self.embedder.dimensions,
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
            stats=stats.model_dump(),
            errors=errors,
            ocr_warnings=ocr_warnings,
        )
        return IndexReport(
            index_dir=str(self.settings.index_dir),
            stats=stats,
            errors=errors,
            ocr_warnings=ocr_warnings,
            embedding_provider=self.embedder.provider_name,
            embedding_dimensions=self.embedder.dimensions,
        )

    def ask(self, question: str, k: int | None = None, threshold: float | None = None) -> tuple[AnswerResponse, list[RetrievedPassage]]:
        cleaned = question.strip()
        if not cleaned:
            raise ConfigurationError("The question is empty. Pass a research question in quotes.")
        self._prepare_query()
        retrieval_k = k or self.settings.retrieval_k
        retrieval_threshold = self.settings.similarity_threshold if threshold is None else threshold
        passages = self.retriever.retrieve(cleaned, retrieval_k, retrieval_threshold)
        generator = self._require_generator()
        draft = self._generate(generator, cleaned, passages, feedback=None)
        outcome = verify_answer(draft, self.store.chunks_by_id(), self.settings, len(passages))
        if generator.can_retry and outcome.input_claims and outcome.response.abstained:
            feedback = (
                "Citation validation failed. Quote verbatim excerpts from the passages, "
                "keep every number aligned with the excerpt, and drop claims you cannot support."
            )
            try:
                draft = generator.generate(cleaned, passages, feedback=feedback)
            except GenerationError:
                outcome.response.passages_retrieved = len(passages)
                return outcome.response, passages
            outcome = verify_answer(draft, self.store.chunks_by_id(), self.settings, len(passages))
        outcome.response.passages_retrieved = len(passages)
        return outcome.response, passages

    def open_index(self) -> VectorStore:
        self.store.load()
        return self.store

    def _prepare_query(self) -> None:
        self.store.load()
        manifest = self.store.manifest
        provider = manifest.get("embedding_provider")
        dimensions = manifest.get("embedding_dimensions")
        if provider != self.embedder.provider_name or dimensions != self.embedder.dimensions:
            raise ConfigurationError(
                "The index embeddings do not match the current embedding settings "
                f"({provider}, {dimensions} dimensions). Restore those settings or run index with --rebuild."
            )
        self.embedder.load_state(self.store.embedder_state)

    def _require_generator(self):
        if self._generator is not None:
            return self._generator
        if self.settings.generation_provider == "extractive":
            self._generator = ExtractiveGenerator(self.settings, self.store, self.retriever)
            return self._generator
        self._generator = LanguageModelGenerator(self.settings, transport=self.transport)
        return self._generator

    def _generate(self, generator, question: str, passages: list[RetrievedPassage], feedback: str | None):
        try:
            return generator.generate(question, passages, feedback=feedback)
        except GenerationError as exc:
            if generator.can_retry and feedback is None:
                return generator.generate(question, passages, feedback=str(exc))
            raise

    def _embed_chunks(self, chunks: list[Chunk], previous: VectorStore | None) -> list[list[float]]:
        if not chunks:
            return []
        reusable: dict[str, list[float]] = {}
        if previous and self.embedder.reuses_vectors:
            same_provider = previous.manifest.get("embedding_provider") == self.embedder.provider_name
            same_dimensions = previous.manifest.get("embedding_dimensions") == self.embedder.dimensions
            if same_provider and same_dimensions:
                reusable = previous.vector_by_id()
        vectors: list[list[float] | None] = [None] * len(chunks)
        missing: list[int] = []
        for index, chunk in enumerate(chunks):
            existing = reusable.get(chunk.chunk_id)
            if existing is not None and len(existing) == self.embedder.dimensions:
                vectors[index] = existing
            else:
                missing.append(index)
        if missing:
            computed = self.embedder.embed_documents([chunks[index].text for index in missing])
            for index, vector in zip(missing, computed):
                vectors[index] = vector
        return [vector if vector is not None else [0.0] * self.embedder.dimensions for vector in vectors]
