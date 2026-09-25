from app.ingestion.chunker import Chunker
from app.ingestion.parser import ParsedPage


def test_short_text_is_one_chunk():
    chunks = Chunker(500, 100).chunk([ParsedPage(None, "The refund period is 30 days.")])
    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].page is None
    assert "30 days" in chunks[0].text


def test_overlap_is_shared_by_neighboring_chunks():
    text = " ".join(f"w{i}" for i in range(300))
    chunks = Chunker(100, 20).chunk([ParsedPage(None, text)])
    overlap = " ".join(f"w{i}" for i in range(80, 100))
    assert len(chunks) > 2
    assert chunks[0].text.endswith(overlap)
    assert chunks[1].text.startswith(overlap)
    assert "w0" in chunks[0].text
    assert "w100" not in chunks[0].text


def test_pdf_pages_are_not_mixed():
    pages = [
        ParsedPage(1, " ".join(f"a{i}" for i in range(80))),
        ParsedPage(2, " ".join(f"b{i}" for i in range(80))),
    ]
    chunks = Chunker(30, 5).chunk(pages)
    assert {chunk.page for chunk in chunks} == {1, 2}
    assert all("b0" not in chunk.text for chunk in chunks if chunk.page == 1)
    assert all("a0" not in chunk.text for chunk in chunks if chunk.page == 2)


def test_overlap_must_be_smaller_than_the_chunk():
    try:
        Chunker(100, 100)
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_blank_text_yields_no_chunks():
    assert Chunker(500, 100).chunk([ParsedPage(1, "   ")]) == []
