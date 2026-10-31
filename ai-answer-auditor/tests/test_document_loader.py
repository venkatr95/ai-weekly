import json

import pytest

from answer_auditor.document_loader import load_sources, read_answer
from answer_auditor.errors import InputError, ParseError
from tests.pdf_util import write_text_pdf


def test_loads_text_markdown_and_json_with_stable_ids(tmp_path):
    (tmp_path / "b.md").write_text("# Hiring note\n\nThe company hired 100 employees.\n", encoding="utf-8")
    (tmp_path / "a.txt").write_text("Title: Annual report\n\nRevenue was €10 million.\n", encoding="utf-8")
    (tmp_path / "c.json").write_text(
        json.dumps({"title": "Financial statement", "text": "Net profit was €15 million."}),
        encoding="utf-8",
    )
    (tmp_path / "notes.dat").write_text("ignore me", encoding="utf-8")
    documents, warnings = load_sources([tmp_path])
    assert [document.source_id for document in documents] == ["S1", "S2", "S3"]
    assert documents[0].title == "Annual report"
    assert documents[0].file_type == "txt"
    assert "Title:" not in documents[0].full_text()
    assert documents[1].title == "Hiring note"
    assert documents[1].file_type == "md"
    assert documents[2].title == "Financial statement"
    assert documents[2].file_type == "json"
    assert any("notes.dat" in warning for warning in warnings)


def test_pdf_keeps_page_numbers(tmp_path):
    path = tmp_path / "report.pdf"
    write_text_pdf(path, ["Cover page only.", "Revenue for 2025 amounted to EUR 120 million."])
    documents, _warnings = load_sources([path])
    assert documents[0].file_type == "pdf"
    assert [page.page_number for page in documents[0].pages] == [1, 2]
    assert "EUR 120 million" in documents[0].pages[1].text


def test_reads_an_answer_file(tmp_path):
    path = tmp_path / "answer.txt"
    path.write_text("Revenue was €10 million.\n", encoding="utf-8")
    assert read_answer(path) == "Revenue was €10 million."


def test_rejects_a_missing_explicit_file(tmp_path):
    with pytest.raises(ParseError, match="not found"):
        load_sources([tmp_path / "missing.txt"])


def test_rejects_an_unsupported_explicit_file(tmp_path):
    path = tmp_path / "notes.dat"
    path.write_text("nope", encoding="utf-8")
    with pytest.raises(ParseError, match="Unsupported source type"):
        load_sources([path])


def test_rejects_an_empty_answer(tmp_path):
    path = tmp_path / "answer.txt"
    path.write_text("  \n", encoding="utf-8")
    with pytest.raises(InputError, match="empty"):
        read_answer(path)


def test_inline_json_source_keeps_the_requested_id():
    documents, _warnings = load_sources(
        [{"source_id": "SRC-1", "title": "Annual report", "text": "Revenue was €10 million."}]
    )
    assert documents[0].source_id == "SRC-1"
    assert documents[0].full_text() == "Revenue was €10 million."
