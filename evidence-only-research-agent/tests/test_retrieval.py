from __future__ import annotations

from pathlib import Path

from evidence_agent.embeddings import HttpEmbedder, LocalHashingEmbedder
from evidence_agent.errors import CorruptIndexError, IndexNotFoundError
from evidence_agent.pipeline import ResearchPipeline
from helpers import build_settings, write_corpus
from pdf_util import write_text_pdf
import pytest


STUDY = (
    "The reported evidence supports the effectiveness of Intervention X. "
    "Intervention X produced a statistically significant improvement in sleep onset latency."
)
RENT = "The office rent is 4200 dollars per month for the downtown lease."


def test_local_embedder_ranks_related_text_higher() -> None:
    embedder = LocalHashingEmbedder(128)
    embedder.fit([STUDY, RENT, "Tomatoes on the west bed are watered on Tuesday and Friday mornings."])
    vectors = embedder.embed_documents(
        [STUDY, RENT, "Tomatoes on the west bed are watered on Tuesday and Friday mornings."]
    )
    query = embedder.embed_query("sleep onset latency improvement")

    def dot(left, right):
        return sum(a * b for a, b in zip(left, right))

    assert dot(query, vectors[0]) > dot(query, vectors[1])
    assert dot(query, vectors[0]) > dot(query, vectors[2])


def test_incremental_index_does_not_duplicate(tmp_path: Path) -> None:
    root = write_corpus(
        tmp_path / "docs",
        {"a.txt": STUDY, "b.txt": RENT},
    )
    pipeline = ResearchPipeline(build_settings(tmp_path))
    first = pipeline.index_path(root, rebuild=True)
    first_ids = [chunk.chunk_id for chunk in pipeline.store.chunks]
    second = pipeline.index_path(root, rebuild=False)
    reloaded = pipeline.open_index()
    assert second.stats.chunks == first.stats.chunks
    assert second.stats.files_reused == 2
    assert [chunk.chunk_id for chunk in reloaded.chunks] == first_ids

    (root / "b.txt").write_text(RENT + " The lease was signed in March.", encoding="utf-8")
    third = pipeline.index_path(root, rebuild=False)
    kept = {chunk.chunk_id for chunk in pipeline.store.chunks}
    assert third.stats.files_reused == 1
    assert third.stats.chunks == first.stats.chunks or third.stats.chunks >= 1
    assert any(chunk_id in kept for chunk_id in first_ids)
    assert not (set(first_ids) <= kept and third.stats.chunks == len(first_ids) * 2)

    (root / "b.txt").unlink()
    fourth = pipeline.index_path(root, rebuild=False)
    assert all(chunk.relative_path != "b.txt" for chunk in pipeline.store.chunks)
    assert fourth.stats.documents == 1


def test_vector_reuse_skips_unchanged_http_embeddings(tmp_path: Path) -> None:
    calls = {"count": 0}

    class FakeEmbedder:
        provider_name = "fake"
        reuses_vectors = True
        dimensions = 4

        def fit(self, texts):
            return None

        def embed_documents(self, texts):
            calls["count"] += len(texts)
            return [[1.0, 0.0, 0.0, 0.0] for _ in texts]

        def embed_query(self, text):
            return [1.0, 0.0, 0.0, 0.0]

        def state_dict(self):
            return {"version": "fake", "dimensions": 4}

        def load_state(self, state):
            assert state["version"] == "fake"

    root = write_corpus(tmp_path / "docs", {"a.txt": STUDY})
    settings = build_settings(tmp_path)
    pipeline = ResearchPipeline(settings, embedder=FakeEmbedder())
    pipeline.index_path(root, rebuild=True)
    assert calls["count"] == 1
    pipeline.index_path(root, rebuild=False)
    assert calls["count"] == 1


def test_corrupt_index_is_rejected(tmp_path: Path) -> None:
    index = tmp_path / "index"
    index.mkdir()
    (index / "manifest.json").write_text("{", encoding="utf-8")
    (index / "embeddings.npy").write_bytes(b"not-an-array")
    pipeline = ResearchPipeline(build_settings(tmp_path))
    with pytest.raises(CorruptIndexError):
        pipeline.open_index()


def test_missing_index_names_the_command(tmp_path: Path) -> None:
    pipeline = ResearchPipeline(build_settings(tmp_path))
    with pytest.raises(IndexNotFoundError) as caught:
        pipeline.ask("What is known?")
    assert "python cli.py index" in str(caught.value)


def test_http_embedder_uses_the_configured_endpoint(tmp_path: Path) -> None:
    seen = {}

    def transport(url, payload, headers, timeout):
        seen["url"] = url
        seen["model"] = payload["model"]
        return {
            "data": [
                {"index": index, "embedding": [0.25] * 32}
                for index, _text in enumerate(payload["input"])
            ]
        }

    embedder = HttpEmbedder(
        base_url="https://embeddings.example/v1",
        api_key="test-key",
        model="demo-embed",
        dimensions=32,
        timeout=5,
        transport=transport,
        secrets=[],
    )
    root = write_corpus(tmp_path / "docs", {"a.txt": STUDY})
    pipeline = ResearchPipeline(build_settings(tmp_path, embedding_dimensions=32), embedder=embedder)
    report = pipeline.index_path(root, rebuild=True)
    assert report.stats.chunks == 1
    assert seen["url"] == "https://embeddings.example/v1/embeddings"
    assert seen["model"] == "demo-embed"


def test_fifty_pdfs_keep_page_citations_and_do_not_duplicate(tmp_path: Path) -> None:
    root = tmp_path / "pdfs"
    for index in range(50):
        if index == 17:
            pages = [
                "Filler document 17 is an ordinary catalog item with no marker.",
                "The special marker result is purple hedgehog 17 in this file.",
            ]
        else:
            pages = [f"Filler document {index} discusses ordinary catalog item {index} and nothing else."]
        write_text_pdf(root / f"paper_{index:02d}.pdf", pages)
    pipeline = ResearchPipeline(build_settings(tmp_path, retrieval_k=8))
    report = pipeline.index_path(root, rebuild=True)
    assert report.stats.files_indexed == 50
    response, _passages = pipeline.ask("What is the special marker result?")
    assert response.abstained is False
    assert any(claim.text.find("purple hedgehog 17") >= 0 for claim in response.claims)
    assert any(citation.source_path == "paper_17.pdf" and citation.page == 2 for citation in response.citations)
    first_ids = [chunk.chunk_id for chunk in pipeline.store.chunks]
    again = pipeline.index_path(root, rebuild=False)
    assert again.stats.files_reused == 50
    assert again.stats.chunks == report.stats.chunks
    assert [chunk.chunk_id for chunk in pipeline.open_index().chunks] == first_ids
