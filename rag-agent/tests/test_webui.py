"""The web UI uses the same in-memory pipeline as the demo."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from streamlit_app import (
    EXAMPLE_QUESTIONS,
    WebUIError,
    ask,
    citation_rows,
    describe_ingest,
    document_rows,
    ingest_prepared,
    new_pipeline,
    prepare_uploads,
    public_error,
    render_answer_text,
    render_json,
    retrieved_rows,
    safe_upload_name,
    sample_files,
    set_answerer,
    status_line,
)

ROOT = Path(__file__).resolve().parents[1]


def test_sample_corpus_answers_and_refuses():
    pipeline = new_pipeline()
    files = sample_files()
    names = [item.filename for item in files]
    assert "refund-policy.md" in names
    assert "refund-policy.pdf" in names
    assert all("\\" not in name and "/" not in name for name in names)

    batch = ingest_prepared(pipeline, files)
    assert batch.errors == []
    note = describe_ingest(batch)
    assert "refund-policy.pdf" in note
    assert "sample_docs" not in note
    assert "Users" not in note
    rows = document_rows(batch.indexed)
    assert "refund-policy.pdf" in [row["Document"] for row in rows]
    assert rows[0]["Chunks"].isdigit()

    refund = ask(pipeline, "What is the refund period?", top_k=5, debug=True, document_count=len(batch.indexed))
    assert "30" in refund.answer
    cited = {citation.document for citation in refund.citations}
    assert cited & {"refund-policy.md", "refund-policy.pdf"}
    assert citation_rows(refund)[0]["Chunk"] == refund.citations[0].chunk_id
    assert retrieved_rows(refund)

    difference = ask(
        pipeline,
        "What is the difference between the refund policy and the cancellation policy?",
        document_count=len(batch.indexed),
    )
    difference_docs = {citation.document for citation in difference.citations}
    assert difference_docs & {"refund-policy.md", "refund-policy.pdf"}
    assert "cancellation-policy.md" in difference_docs

    refused = ask(pipeline, "What is the company's annual revenue?", debug=False, document_count=len(batch.indexed))
    assert refused.citations == []
    assert "sufficient information" in refused.answer
    assert citation_rows(refused) == []
    assert "retrieved" not in json.loads(render_json(refused))


def test_refund_pdf_citation_names_page_4():
    pipeline = new_pipeline()
    pdf = next(item for item in sample_files() if item.filename == "refund-policy.pdf")
    batch = ingest_prepared(pipeline, [pdf])
    assert batch.indexed[0].chunks >= 1
    response = ask(pipeline, EXAMPLE_QUESTIONS[0], debug=True, document_count=1)
    assert response.citations[0].document == "refund-policy.pdf"
    assert response.citations[0].page == 4
    text = render_answer_text(response)
    assert "page 4" in text
    assert "refund-policy.pdf" in text
    payload = json.loads(render_json(response))
    assert payload["retrieved"][0]["chunk_id"]
    assert retrieved_rows(response)[0]["Chunk"] == response.retrieved[0].chunk_id


def test_question_and_upload_names_are_not_opened_as_paths(tmp_path: Path):
    outside = tmp_path / "budget.txt"
    outside.write_text("The marker is ZEBRA-SOURCE-99.\n", encoding="utf-8")
    pipeline = new_pipeline()
    batch = ingest_prepared(
        pipeline,
        prepare_uploads([(str(outside), b"The refund period is 30 days.\n")]),
    )
    assert batch.indexed[0].filename == "budget.txt"
    response = ask(pipeline, "What is the refund period?", document_count=1)
    assert "ZEBRA-SOURCE-99" not in response.model_dump_json()
    assert "30 days" in response.answer
    as_path = ask(pipeline, str(outside), document_count=1)
    assert "ZEBRA-SOURCE-99" not in as_path.model_dump_json()

    secret = tmp_path / "secret.txt"
    secret.write_text("The marker is ZEBRA-SOURCE-99.\n", encoding="utf-8")
    indexed = new_pipeline()
    ingest_prepared(indexed, prepare_uploads([("notes.txt", b"The refund period is 30 days.\n")]))
    asked = ask(indexed, str(secret), document_count=1)
    assert "ZEBRA-SOURCE-99" not in asked.model_dump_json()


def test_uploads_keep_safe_names_and_continue_after_a_bad_file():
    used: set[str] = set()
    assert safe_upload_name("..\\secret.md", 1, used) == "secret.md"
    assert safe_upload_name("C:/outside/budget.txt", 2, used) == "budget.txt"
    assert safe_upload_name("Notes.TXT", 3, used) == "Notes.txt"
    assert safe_upload_name("notes.txt", 4, used) == "notes-2.txt"
    with pytest.raises(WebUIError, match="Unsupported"):
        safe_upload_name("notes.dat", 1, set())
    with pytest.raises(WebUIError, match="no file name"):
        safe_upload_name("..", 1, set())

    with pytest.raises(WebUIError, match="at least one"):
        prepare_uploads([])
    with pytest.raises(WebUIError, match="not a file"):
        prepare_uploads([("notes.txt", "hello")])  # type: ignore[list-item]
    with pytest.raises(WebUIError, match="empty"):
        prepare_uploads([("notes.txt", b"")])
    with pytest.raises(WebUIError, match="4 bytes"):
        prepare_uploads([("notes.txt", b"hello")], max_bytes=4)

    prepared = prepare_uploads(
        [
            ("notes.txt", b"The refund period is 30 days.\n"),
            ("notes.txt", b"Office rent is 4200 dollars per month.\n"),
            ("..\\secret.md", b"# Protocol\n\nThe protocol was reviewed by the desk yesterday.\n"),
        ]
    )
    assert [item.filename for item in prepared] == ["notes.txt", "notes-2.txt", "secret.md"]

    pipeline = new_pipeline()
    batch = ingest_prepared(
        pipeline,
        prepare_uploads(
            [
                ("policy.txt", b"The refund period is 30 days.\n"),
                ("bad.txt", b"\xff"),
            ]
        ),
    )
    assert [item.filename for item in batch.indexed] == ["policy.txt"]
    assert batch.errors and "bad.txt" in batch.errors[0]
    assert "UTF-8" in batch.errors[0]
    response = ask(pipeline, "What is the refund period?", document_count=1)
    assert "30 days" in response.answer


def test_page_pipeline_ignores_postgres_and_a_configured_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VECTOR_STORE", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://rag:rag@127.0.0.1:1/rag")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "xai")
    monkeypatch.setenv("LLM_PROVIDER", "xai")
    monkeypatch.setenv("XAI_API_KEY", "xai-secret-token-value")
    pipeline = new_pipeline()
    assert pipeline.settings.vector_store == "memory"
    assert pipeline.settings.database_url == "postgresql+psycopg://rag:rag@localhost:5432/rag"
    assert pipeline.embedder.name == "hashing"
    assert pipeline.generator.name == "extractive"
    assert pipeline.settings.resolved_api_key() is None
    line = status_line(pipeline, [])
    assert "xai-secret-token-value" not in line
    assert "127.0.0.1" not in line
    assert os.environ["VECTOR_STORE"] == "postgres"


def test_switching_to_xai_keeps_the_index_and_hides_the_key(monkeypatch: pytest.MonkeyPatch):
    for name in ("LLM_MODEL", "XAI_BASE_URL", "REASONING_EFFORT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("XAI_API_KEY", "xai-secret-token-value")
    pipeline = new_pipeline()
    pdf = next(item for item in sample_files() if item.filename == "refund-policy.pdf")
    batch = ingest_prepared(pipeline, [pdf])
    document_id = batch.indexed[0].document_id

    assert set_answerer(pipeline, "xai") == "xai:grok-4.7"
    line = status_line(pipeline, batch.indexed)
    assert "xai:grok-4.7" in line
    assert "xai-secret-token-value" not in line
    assert pipeline.get_document(document_id).filename == "refund-policy.pdf"

    assert set_answerer(pipeline, "extractive") == "extractive"
    assert pipeline.settings.resolved_api_key() is None
    response = ask(pipeline, "What is the refund period?", document_count=1)
    assert response.citations[0].page == 4

    monkeypatch.delenv("XAI_API_KEY", raising=False)
    with pytest.raises(WebUIError, match="XAI_API_KEY"):
        set_answerer(pipeline, "xai")
    assert pipeline.generator.name == "extractive"
    with pytest.raises(WebUIError, match="extractive or xai"):
        set_answerer(pipeline, "openai")
    assert pipeline.generator.name == "extractive"

    monkeypatch.setenv("REASONING_EFFORT", "nope")
    with pytest.raises(WebUIError, match="REASONING_EFFORT"):
        set_answerer(pipeline, "extractive")
    assert pipeline.generator.name == "extractive"


def test_ask_rejects_empty_oversized_and_bad_passage_counts():
    pipeline = new_pipeline()
    with pytest.raises(WebUIError, match="at least one document"):
        ask(pipeline, "What is the refund period?", document_count=0)
    ingest_prepared(pipeline, prepare_uploads([("notes.txt", b"The refund period is 30 days.\n")]))
    with pytest.raises(WebUIError, match="Enter a question"):
        ask(pipeline, "  \n", document_count=1)
    with pytest.raises(WebUIError, match="4000"):
        ask(pipeline, "a" * 4001, document_count=1)
    with pytest.raises(WebUIError, match="1 to 20"):
        ask(pipeline, "What is the refund period?", top_k=0, document_count=1)
    with pytest.raises(WebUIError, match="1 to 20"):
        ask(pipeline, "What is the refund period?", top_k=21, document_count=1)
    with pytest.raises(WebUIError, match="whole number"):
        ask(pipeline, "What is the refund period?", top_k=5.5, document_count=1)
    with pytest.raises(WebUIError, match="whole number"):
        ask(pipeline, "What is the refund period?", top_k=True, document_count=1)
    response = ask(pipeline, "What is the refund period?", top_k=5.0, document_count=1)
    assert "30 days" in response.answer


def test_public_error_redacts_keys(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("XAI_API_KEY", "xai-secret-token-value")
    text = public_error(RuntimeError("bad key xai-secret-token-value and sk-abcdefghijklmnopqrstuvwxyz"))
    assert "xai-secret-token-value" not in text
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in text
    assert "[redacted]" in text


def test_missing_sample_paths(tmp_path: Path):
    with pytest.raises(WebUIError, match="sample corpus is missing"):
        sample_files(corpus=tmp_path / "missing")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "note.md").write_text("The refund period is 30 days.\n", encoding="utf-8")
    files = sample_files(corpus=corpus, pdf=tmp_path / "absent.pdf")
    assert [item.filename for item in files] == ["note.md", "refund-policy.pdf"]
    assert files[1].data.startswith(b"%PDF")


def test_page_loads_the_sample_and_answers_the_refund_question():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=60)
    app.run()
    assert not app.exception
    app.button(key="load_sample").click().run()
    assert not app.exception
    blob = _page_text(app)
    assert "refund-policy.pdf" in blob
    app.button(key="ask").click().run()
    assert not app.exception
    answered = _page_text(app)
    assert "30" in answered
    assert "page 4" in answered


def _page_text(app) -> str:
    parts: list[str] = []
    for name in (
        "text",
        "caption",
        "markdown",
        "info",
        "error",
        "warning",
        "metric",
        "expander",
        "dataframe",
    ):
        for element in getattr(app, name, []):
            parts.append(str(getattr(element, "value", "")))
            parts.append(str(getattr(element, "body", "")))
            parts.append(str(getattr(element, "label", "")))
    return "\n".join(parts)
