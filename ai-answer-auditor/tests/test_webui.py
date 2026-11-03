"""The web UI uses the same auditor as the CLI."""

import json
import tempfile
from pathlib import Path

import pytest

from answer_auditor.errors import ConfigurationError, InputError, ParseError
from streamlit_app import audit_request, claim_rows, example_inputs, load_uploaded_sources

ROOT = Path(__file__).resolve().parents[1]
DEMO_STATUSES = ["supported", "contradicted", "contradicted", "partially_supported"]
DEMO_LABELS = ["Supported", "Contradicted", "Contradicted", "Partially supported"]


def test_example_rows_match_the_demo():
    question, answer, sources = example_inputs()
    report, note = audit_request(answer, question, sources, provider="heuristic")
    assert note == "Audited the pasted answer against the pasted sources."
    assert [claim.status for claim in report.claims] == DEMO_STATUSES
    assert [row["Status"] for row in claim_rows(report)] == DEMO_LABELS
    assert claim_rows(report)[0]["Claim"] == "C001"
    assert "€120 million" in claim_rows(report)[0]["Text"]
    assert report.summary.evidence_coverage == 25.0
    assert [source.title for source in report.sources] == [
        "Annual report",
        "Financial statement",
        "Workforce report",
    ]
    assert all(source.path is None for source in report.sources)
    assert "C002" in report.model_dump_json()


def test_blank_question_is_omitted_and_a_title_overrides_the_file():
    _question, answer, _sources = example_inputs()
    annual = (ROOT / "examples" / "sources" / "source1.txt").read_text(encoding="utf-8")
    report, _note = audit_request(answer, "  ", [("Custom report", annual)])
    assert report.question is None
    assert report.sources[0].title == "Custom report"
    quote = report.claims[0].supporting_evidence[0].quote
    assert "Title:" not in quote
    assert "€120 million" in quote


def test_markdown_heading_is_a_title():
    report, _note = audit_request(
        "The company hired 100 employees.",
        None,
        [("", "# Hiring note\n\nThe company hired 100 employees.\n")],
    )
    assert report.sources[0].title == "Hiring note"
    assert report.sources[0].file_type == "md"
    assert report.claims[0].status == "supported"


def test_pasted_path_is_not_opened(tmp_path: Path):
    secret = tmp_path / "secret.txt"
    secret.write_text("Title: Hidden\n\nThe marker is ZEBRA-SOURCE-99.\n", encoding="utf-8")
    report, _note = audit_request(
        "The marker is ZEBRA-SOURCE-99.",
        None,
        [("", str(secret))],
    )
    assert all(source.title != "Hidden" for source in report.sources)
    for claim in report.claims:
        for excerpt in [*claim.supporting_evidence, *claim.contradicting_evidence]:
            assert "ZEBRA-SOURCE-99" not in excerpt.quote
    assert "Hidden" not in report.model_dump_json()


def test_uploads_replace_pasted_sources_and_keep_file_names():
    question, answer, _sources = example_inputs()
    uploads = [
        (path.name, path.read_bytes())
        for path in sorted((ROOT / "examples" / "sources").glob("*.txt"))
    ]
    report, note = audit_request(
        answer,
        question,
        pasted=[("", "Revenue increased by 99% and the marker is PASTE-ONLY.")],
        uploads=uploads,
    )
    assert [claim.status for claim in report.claims] == DEMO_STATUSES
    assert [source.path for source in report.sources] == ["source1.txt", "source2.txt", "source3.txt"]
    assert "PASTE-ONLY" not in report.model_dump_json()
    assert "uploaded files" in note
    assert "Temp" not in note


def test_pdf_upload_is_read_and_the_temp_directory_is_removed(tmp_path: Path, monkeypatch):
    from tests.pdf_util import write_text_pdf

    pdf_path = tmp_path / "annual.pdf"
    write_text_pdf(pdf_path, ["Revenue for 2025 amounted to EUR 120 million."])
    holder: dict[str, str] = {}
    real_mkdtemp = tempfile.mkdtemp

    def capture(*args, **kwargs):
        folder = real_mkdtemp(*args, **kwargs)
        holder["folder"] = folder
        return folder

    monkeypatch.setattr("streamlit_app.tempfile.mkdtemp", capture)
    report, note = audit_request(
        "Revenue was EUR 120 million in 2025.",
        None,
        pasted=[],
        uploads=[("annual.pdf", pdf_path.read_bytes())],
    )
    assert report.sources[0].path == "annual.pdf"
    assert report.sources[0].page_count == 1
    assert report.claims[0].supporting_evidence[0].page == 1
    assert "EUR 120 million" in report.claims[0].supporting_evidence[0].quote
    assert note == "Audited the pasted answer against the uploaded file annual.pdf."
    assert holder["folder"]
    assert not Path(holder["folder"]).exists()


def test_json_upload_duplicate_names_and_unsafe_names():
    body = json.dumps(
        {"title": "Financial statement", "text": "Net profit for the financial year was €15 million."}
    ).encode("utf-8")
    report, _note = audit_request(
        "The company achieved a net profit of €18 million.",
        None,
        [],
        uploads=[("statement.json", body)],
    )
    assert report.claims[0].status == "contradicted"
    assert report.sources[0].title == "Financial statement"
    assert report.sources[0].path == "statement.json"

    uploads = [
        ("notes.txt", b"Revenue for 2025 amounted to EUR 10 million.\n"),
        ("notes.txt", b"Net profit for the financial year was EUR 2 million.\n"),
        ("..\\secret.txt", b"The company employed 10 people.\n"),
    ]
    loaded, _warnings = load_uploaded_sources(uploads)
    assert [document.path for document in loaded] == ["notes.txt", "notes-2.txt", "secret.txt"]
    assert "EUR 2 million" in loaded[1].full_text()
    assert "10 people" in loaded[2].full_text()


def test_upload_errors_and_empty_input():
    with pytest.raises(ParseError, match="UTF-8"):
        audit_request("Revenue was 10.", None, [], uploads=[("notes.txt", b"\xff")])
    with pytest.raises(ParseError, match="Unsupported"):
        audit_request("Revenue was 10.", None, [], uploads=[("notes.dat", b"hello")])
    with pytest.raises(ParseError, match="invalid JSON"):
        audit_request("Revenue was 10.", None, [], uploads=[("bad.json", b"{")])
    with pytest.raises(InputError, match="empty"):
        audit_request(" \n", None, [("", "Revenue was €10 million.")])
    with pytest.raises(InputError, match="at least one source"):
        audit_request("Revenue was €10 million.", None, [("", "  "), ("Title", "\n")])


def test_provider_selection_stays_local_and_xai_needs_a_key(monkeypatch):
    monkeypatch.setenv("AUDITOR_PROVIDER", "xai")
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.setattr("answer_auditor.config.load_dotenv", lambda path=None: None)
    question, answer, sources = example_inputs()
    report, _note = audit_request(answer, question, sources, provider="heuristic")
    assert report.provider == "heuristic"
    with pytest.raises(ConfigurationError, match="XAI_API_KEY"):
        audit_request(answer, question, sources, provider="xai")
    with pytest.raises(ConfigurationError, match="Unknown provider"):
        audit_request(answer, question, sources, provider="other")


def test_page_audits_the_sample_and_rejects_an_empty_answer():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=60)
    app.run()
    assert not app.exception

    app.button(key="audit").click().run()
    assert not app.exception
    assert app.session_state.report.summary.evidence_coverage == 25.0
    assert app.session_state.report.provider == "heuristic"
    assert [claim.status for claim in app.session_state.report.claims] == DEMO_STATUSES
    frame = app.dataframe[0].value
    assert list(frame["Status"]) == DEMO_LABELS
    assert list(frame["Claim"]) == ["C001", "C002", "C003", "C004"]

    app.button(key="add_source").click().run()
    assert app.session_state.source_count == 4
    assert app.session_state.report.summary.evidence_coverage == 25.0

    app.button(key="load_example").click().run()
    assert app.session_state.source_count == 3
    assert app.session_state.report is None
    app.button(key="audit").click().run()
    assert app.session_state.report.summary.evidence_coverage == 25.0

    app.text_area(key="answer").set_value("   ").run()
    app.button(key="audit").click().run()
    assert any("empty" in item.value.lower() for item in app.error)
    assert app.session_state.report is None

    app.selectbox(key="provider").set_value("xai").run()
    assert any("xAI" in item.value for item in app.warning)
    assert app.session_state.report is None
