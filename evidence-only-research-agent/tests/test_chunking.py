from __future__ import annotations

from evidence_agent.chunking import chunk_document
from evidence_agent.schemas import ExtractedDocument, PageText


def _document(relative_path: str, pages: list[tuple[int | None, str]]) -> ExtractedDocument:
    return ExtractedDocument(
        absolute_path=relative_path,
        relative_path=relative_path,
        file_type="txt",
        content_hash="abc",
        pages=[PageText(page_number=page, text=text) for page, text in pages],
    )


def test_overlap_is_stable_and_covers_every_token() -> None:
    words = [f"w{i:02d}" for i in range(10)]
    document = _document("notes.txt", [(None, " ".join(words))])
    first = chunk_document(document, chunk_size=4, chunk_overlap=1)
    second = chunk_document(document, chunk_size=4, chunk_overlap=1)
    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
    assert [chunk.text for chunk in first] == [
        "w00 w01 w02 w03",
        "w03 w04 w05 w06",
        "w06 w07 w08 w09",
    ]
    covered = " ".join(chunk.text for chunk in first)
    for word in words:
        assert word in covered


def test_chunks_do_not_mix_documents() -> None:
    alpha = chunk_document(
        _document("a.txt", [(None, " ".join(f"alpha{i}" for i in range(30)))]),
        chunk_size=20,
        chunk_overlap=5,
    )
    beta = chunk_document(
        _document("b.txt", [(None, " ".join(f"beta{i}" for i in range(30)))]),
        chunk_size=20,
        chunk_overlap=5,
    )
    for chunk in alpha:
        assert "beta0" not in chunk.text
        assert chunk.relative_path == "a.txt"
    for chunk in beta:
        assert "alpha0" not in chunk.text


def test_page_metadata_follows_the_excerpt() -> None:
    document = _document(
        "paper.pdf",
        [
            (1, "alpha word " * 20),
            (2, "The beta result is stored on the second page of the paper."),
        ],
    )
    chunks = chunk_document(document, chunk_size=200, chunk_overlap=20)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.page_start == 1
    assert chunk.page_end == 2
    from evidence_agent.citation_verification import excerpt_page

    assert excerpt_page(chunk, "The beta result is stored on the second page of the paper.") == 2
