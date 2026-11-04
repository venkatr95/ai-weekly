"""The web UI uses the same pipeline as the CLI."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from evidence_agent.errors import ConfigurationError, EmptyCorpusError
from evidence_agent.pipeline import ResearchPipeline
from streamlit_app import (
    ask_question,
    build_settings,
    claim_rows,
    chunk_text,
    describe_index,
    example_questions,
    index_directory,
    index_uploads,
    passage_rows,
    safe_upload_name,
    source_rows,
    write_uploads,
)

ROOT = Path(__file__).resolve().parents[1]


def test_example_corpus_answers_abstains_and_reports_conflict(example_documents: Path, tmp_path: Path):
    index_dir = tmp_path / "index"
    report = index_directory(example_documents, index_dir=index_dir, rebuild=True)
    assert report.embedding_provider == "local"
    assert report.stats.files_skipped >= 1
    assert report.stats.files_needs_ocr >= 1
    note = describe_index(report, "examples/documents")
    assert note.startswith("Indexed ")
    assert "examples/documents" in note
    assert "OCR required" in note

    store = ResearchPipeline(build_settings(index_dir, "extractive")).open_index()
    rows = source_rows(store.documents)
    paths = [row["Path"] for row in rows]
    assert "methods_glossary.txt" in paths
    assert "notes/ignore.dat" not in paths
    assert [row["Path"] for row in rows if row["OCR"] == "yes"] == ["scans/empty_scan.pdf"]

    defined, _passages = ask_question("What is Intervention X?", index_dir=index_dir)
    assert defined.provider == "extractive"
    assert defined.abstained is False
    assert "morning light-exposure program" in defined.claims[0].text
    defined_rows = claim_rows(defined)
    assert defined_rows[0]["Claim"] == "claim-1"
    assert defined_rows[0]["Status"] == "Supported"
    assert defined_rows[0]["Verification"] == "Verified"
    assert "methods_glossary.txt" in defined_rows[0]["Sources"]
    assert "morning light-exposure program" in chunk_text(index_dir, defined.citations[0].chunk_id)

    partial, passages = ask_question(
        "What evidence supports the effectiveness of Intervention X, and what long-term benefits are reported?",
        index_dir=index_dir,
    )
    assert partial.abstained is False
    assert partial.unanswered_questions
    assert passages
    assert passage_rows(passages)[0]["Chunk"] == passages[0].chunk_id

    abstained, _empty = ask_question(
        "What effect did Intervention X have on blood pressure in children?",
        index_dir=index_dir,
    )
    assert abstained.abstained is True
    assert abstained.claims == []
    assert claim_rows(abstained) == []

    conflict, _conflict_passages = ask_question(
        "Did Intervention X produce a statistically significant improvement in sleep onset latency?",
        index_dir=index_dir,
    )
    assert len(conflict.claims) >= 2
    assert conflict.conflicts
    assert conflict.conflicts[0].resolved is False


def test_question_is_not_opened_as_a_path(example_documents: Path, tmp_path: Path):
    secret = tmp_path / "secret.txt"
    secret.write_text("The marker is ZEBRA-SOURCE-99.\n", encoding="utf-8")
    index_dir = tmp_path / "index"
    index_directory(example_documents, index_dir=index_dir, rebuild=True)
    response, _passages = ask_question(str(secret), index_dir=index_dir)
    assert "ZEBRA-SOURCE-99" not in response.model_dump_json()


def test_uploads_replace_the_corpus_and_keep_safe_names(tmp_path: Path):
    index_dir = tmp_path / "index"
    corpus = tmp_path / "uploads"
    first, first_note = index_uploads(
        [("only.txt", b"The marker is ZEBRA-SOURCE-99.\n")],
        index_dir=index_dir,
        corpus_dir=corpus,
    )
    assert "only.txt" in first_note
    assert str(corpus) not in first_note
    assert "Temp" not in first_note

    report, note = index_uploads(
        [
            ("notes.txt", b"Intervention X is a structured morning light-exposure program lasting 30 minutes.\n"),
            ("notes.txt", b"Office rent is 4200 dollars per month.\n"),
            ("..\\secret.md", b"# Protocol\n\nThe protocol was reviewed.\n"),
            ("C:/outside/budget.md", b"The spare note is not the rent.\n"),
        ],
        index_dir=index_dir,
        corpus_dir=corpus,
        rebuild=True,
    )
    assert report.stats.files_indexed == 4
    assert sorted(path.name for path in corpus.iterdir()) == [
        "budget.md",
        "notes-2.txt",
        "notes.txt",
        "secret.md",
    ]
    assert str(corpus) not in note
    store = ResearchPipeline(build_settings(index_dir, "extractive")).open_index()
    blob = "\n".join(chunk.text for chunk in store.chunks)
    assert "ZEBRA-SOURCE-99" not in blob
    assert "morning light-exposure program" in blob
    response, _passages = ask_question("What is Intervention X?", index_dir=index_dir)
    assert response.citations[0].source_path == "notes.txt"

    failed, _failed_note = index_uploads(
        [("notes.txt", b"\xff")],
        index_dir=index_dir,
        corpus_dir=corpus,
        rebuild=True,
    )
    assert failed.stats.files_indexed == 0
    assert failed.stats.files_failed == 1
    assert any("UTF-8" in error for error in failed.errors)


def test_upload_names_and_empty_inputs(tmp_path: Path):
    used: set[str] = set()
    assert safe_upload_name("..\\secret.txt", 1, used) == "secret.txt"
    assert safe_upload_name("secret.txt", 2, used) == "secret-2.txt"
    with pytest.raises(ConfigurationError, match="Unsupported"):
        safe_upload_name("notes.dat", 1, set())
    with pytest.raises(ConfigurationError, match="no file name"):
        safe_upload_name("..", 1, set())

    corpus = tmp_path / "uploads"
    with pytest.raises(ConfigurationError, match="at least one"):
        write_uploads([], corpus)
    with pytest.raises(ConfigurationError, match="not a file"):
        write_uploads([("notes.txt", "hello")], corpus)  # type: ignore[list-item]

    index_dir = tmp_path / "index"
    index_dir.mkdir()
    (index_dir / "manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="index directory"):
        write_uploads([("notes.txt", b"hello\n")], index_dir)

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(EmptyCorpusError, match="No supported documents"):
        index_directory(empty, index_dir=tmp_path / "fresh")
    with pytest.raises(EmptyCorpusError, match="does not exist"):
        index_directory(tmp_path / "missing", index_dir=tmp_path / "fresh")
    with pytest.raises(ConfigurationError, match="empty"):
        ask_question("  \n", index_dir=tmp_path / "fresh")
    with pytest.raises(ConfigurationError, match="at least 1"):
        ask_question("What is Intervention X?", index_dir=tmp_path / "fresh", k=0)
    with pytest.raises(ConfigurationError, match="between 0 and 1"):
        ask_question("What is Intervention X?", index_dir=tmp_path / "fresh", threshold=1.5)
    with pytest.raises(ConfigurationError, match="extractive, xai, or openai_compatible"):
        build_settings(tmp_path, "other")


def test_page_provider_overrides_the_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("evidence_agent.config.load_dotenv", lambda path=None: None)
    monkeypatch.setenv("GENERATION_PROVIDER", "nope")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "http")
    monkeypatch.setenv("INDEX_DIR", str(tmp_path / "cli-index"))
    index_dir = tmp_path / "page-index"
    settings = build_settings(index_dir, "extractive")
    assert settings.generation_provider == "extractive"
    assert settings.embedding_provider == "local"
    assert settings.index_dir == index_dir
    assert os.environ["GENERATION_PROVIDER"] == "nope"
    assert os.environ["EMBEDDING_PROVIDER"] == "http"
    assert os.environ["INDEX_DIR"] == str(tmp_path / "cli-index")

    monkeypatch.setenv("CHUNK_SIZE", "nope")
    monkeypatch.setenv("GENERATION_PROVIDER", "xai")
    with pytest.raises(ConfigurationError, match="CHUNK_SIZE"):
        build_settings(index_dir, "extractive")
    assert os.environ["GENERATION_PROVIDER"] == "xai"
    assert os.environ["CHUNK_SIZE"] == "nope"


def test_remote_providers_need_configuration_and_extractive_does_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr("evidence_agent.config.load_dotenv", lambda path=None: None)
    monkeypatch.setenv("GENERATION_PROVIDER", "xai")
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_COMPATIBLE_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_COMPATIBLE_MODEL", raising=False)
    corpus = tmp_path / "docs"
    corpus.mkdir()
    (corpus / "note.txt").write_text(
        "Intervention X is a structured morning light-exposure program lasting 30 minutes.\n",
        encoding="utf-8",
    )
    index_dir = tmp_path / "index"
    report = index_directory(corpus, index_dir=index_dir, provider="extractive")
    assert report.embedding_provider == "local"
    response, _passages = ask_question("What is Intervention X?", index_dir=index_dir, provider="extractive")
    assert response.provider == "extractive"
    assert "morning light-exposure program" in response.claims[0].text
    with pytest.raises(ConfigurationError, match="XAI_API_KEY"):
        ask_question("What is Intervention X?", index_dir=index_dir, provider="xai")
    with pytest.raises(ConfigurationError, match="OPENAI_COMPATIBLE_BASE_URL"):
        ask_question("What is Intervention X?", index_dir=index_dir, provider="openai_compatible")


def test_page_indexes_the_sample_and_rejects_an_empty_question(example_documents: Path):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    assert example_documents.is_dir()
    app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=60)
    app.run()
    assert not app.exception
    assert app.session_state.provider == "extractive"
    assert app.session_state.question == example_questions()[0]

    app.button(key="index_example").click().run()
    assert not app.exception
    assert app.session_state.index_report.stats.files_indexed > 0
    assert app.session_state.index_report.embedding_provider == "local"
    assert "examples/documents" in app.session_state.input_note
    assert app.session_state.response is None

    app.button(key="ask").click().run()
    assert not app.exception
    assert app.session_state.response.provider == "extractive"
    assert "morning light-exposure program" in app.session_state.response.claims[0].text
    frame = app.dataframe[0].value
    assert "Supported" in list(frame["Status"])
    assert "morning light-exposure program" in " ".join(list(frame["Finding"]))

    missing = ROOT / "does-not-exist-webui"
    app.text_input(key="folder_path").set_value(str(missing)).run()
    app.button(key="index_folder").click().run()
    assert any("does not exist" in item.value for item in app.error)
    assert app.session_state.index_report.stats.files_indexed > 0
    assert app.session_state.response is not None

    questions = example_questions()
    app.selectbox(key="example_question").set_value(questions[2]).run()
    app.button(key="use_example").click().run()
    assert app.session_state.question == questions[2]
    assert app.session_state.response is None
    app.button(key="ask").click().run()
    assert app.session_state.response.abstained is True
    assert app.session_state.response.claims == []

    app.text_area(key="question").set_value("   ").run()
    app.button(key="ask").click().run()
    assert any("empty" in item.value.lower() for item in app.error)
    assert app.session_state.response is None
    with pytest.raises(ConfigurationError, match="No chunk"):
        chunk_text(Path(app.session_state.index_dir), "missing-chunk")
