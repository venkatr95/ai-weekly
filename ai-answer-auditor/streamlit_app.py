"""Web UI for the AI Answer Auditor. Run with: streamlit run streamlit_app.py"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_SRC = ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from answer_auditor.config import load_settings
from answer_auditor.document_loader import SUPPORTED_SUFFIXES, load_sources
from answer_auditor.errors import AuditorError, InputError, ParseError
from answer_auditor.pipeline import audit, audit_documents
from answer_auditor.report_generator import render_json, render_markdown, review_actions
from answer_auditor.schemas import STATUS_LABELS, AuditReport, ClaimResult, EvidenceExcerpt, Summary

PROVIDERS = ("heuristic", "xai")
EXAMPLE_QUESTION = "What were the results of the company's 2025 financial performance?"
MAX_PASTED_SOURCES = 12
TYPE_LABELS = {
    "factual": "Factual",
    "opinion": "Opinion",
    "recommendation": "Recommendation",
    "non_factual": "Non-factual",
}
_MARKDOWN_HEADING = re.compile(r"^#\s+\S")
_UNSAFE_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def example_inputs() -> tuple[str, str, list[tuple[str, str]]]:
    """Question, answer, and pasted sources for the bundled financial demo."""

    answer = (ROOT / "examples" / "answer.txt").read_text(encoding="utf-8")
    sources: list[tuple[str, str]] = []
    directory = ROOT / "examples" / "sources"
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.suffix.lower() in {".txt", ".md", ".markdown"}:
            sources.append(("", path.read_text(encoding="utf-8")))
    return EXAMPLE_QUESTION, answer, sources


def clean_question(question: str | None) -> str | None:
    if question is None:
        return None
    stripped = question.strip()
    return stripped or None


def pasted_file_type(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _MARKDOWN_HEADING.match(stripped):
            return "md"
        return "txt"
    return "txt"


def pasted_entries(sources: list[tuple[str, str]]) -> list[dict]:
    """Turn text boxes into inline sources.

    A path typed into a box stays text. The loader opens a path only when the
    entry itself is a path. These entries are dictionaries with a text field.
    """

    entries: list[dict] = []
    for title, text in sources:
        if not text or not str(text).strip():
            continue
        entry: dict = {"text": text, "file_type": pasted_file_type(text)}
        if title and str(title).strip():
            entry["title"] = str(title).strip()
        entries.append(entry)
    return entries


def upload_filename(name: str, index: int, used: set[str]) -> str:
    base = Path(str(name).replace("\\", "/")).name
    if not base or base in {".", ".."}:
        raise ParseError(f"Uploaded file {index} has no file name.")
    suffix = Path(base).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ParseError(
            f"Unsupported source type '{suffix or base}'. "
            "Supported types: .txt, .md, .markdown, .pdf, .json."
        )
    stem = _UNSAFE_NAME.sub("_", Path(base).stem).strip(" .") or f"source-{index}"
    stem = stem[:80]
    candidate = f"{stem}{suffix}"
    counter = 2
    while candidate.lower() in used:
        candidate = f"{stem}-{counter}{suffix}"
        counter += 1
    used.add(candidate.lower())
    return candidate


def load_uploaded_sources(files: list[tuple[str, bytes]]) -> tuple[list, list[str]]:
    """Parse uploads with the same loader as the CLI, then delete the temp files.

    The report records each file name. It does not record the temporary directory.
    """

    if not files:
        raise InputError("Provide at least one source file or directory.")
    directory = Path(tempfile.mkdtemp(prefix="answer-auditor-"))
    names: list[str] = []
    try:
        paths: list[Path] = []
        used: set[str] = set()
        for index, (name, data) in enumerate(files, start=1):
            if not isinstance(data, (bytes, bytearray)):
                raise ParseError(f"Could not read '{name}': the upload is not a file.")
            safe = upload_filename(name, index, used)
            path = directory / safe
            try:
                path.write_bytes(data)
            except OSError as exc:
                raise ParseError(f"Could not read '{safe}': {exc.__class__.__name__}.") from exc
            paths.append(path)
            names.append(safe)
        documents, warnings = load_sources(paths)
    finally:
        shutil.rmtree(directory, ignore_errors=True)
    rewritten = [
        document.model_copy(update={"path": filename})
        for document, filename in zip(documents, names, strict=True)
    ]
    return rewritten, warnings


def audit_request(
    answer: str,
    question: str | None,
    pasted: list[tuple[str, str]],
    uploads: list[tuple[str, bytes]] | None = None,
    provider: str = "heuristic",
) -> tuple[AuditReport, str]:
    """Run one audit. Uploaded files replace pasted sources when both are present."""

    if not answer or not answer.strip():
        raise InputError("The answer is empty.")
    settings = load_settings(provider)
    asked = clean_question(question)
    if uploads:
        documents, warnings = load_uploaded_sources(uploads)
        report = audit_documents(
            answer,
            documents,
            question=asked,
            settings=settings,
            extra_warnings=warnings,
        )
        names = [source.path or source.source_id for source in report.sources]
        if len(names) == 1:
            note = f"Audited the pasted answer against the uploaded file {names[0]}."
        else:
            note = "Audited the pasted answer against the uploaded files " + ", ".join(names) + "."
        return report, note
    entries = pasted_entries(pasted)
    if not entries:
        raise InputError("Provide at least one source file or directory.")
    report = audit(answer, entries, question=asked, settings=settings)
    return report, "Audited the pasted answer against the pasted sources."


def coverage_label(summary: Summary) -> str:
    if summary.evidence_coverage is None:
        return "n/a"
    return f"{summary.evidence_coverage:.1f}%"


def claim_rows(report: AuditReport) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for claim in report.claims:
        rows.append(
            {
                "Claim": claim.claim_id,
                "Status": STATUS_LABELS[claim.status],
                "Type": TYPE_LABELS[claim.claim_type],
                "Text": claim.text,
            }
        )
    return rows


def source_rows(report: AuditReport) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source in report.sources:
        pages = "-" if source.page_count is None else str(source.page_count)
        rows.append(
            {
                "ID": source.source_id,
                "Title": source.title or "",
                "Type": source.file_type,
                "Pages": pages,
            }
        )
    return rows


def evidence_line(excerpt: EvidenceExcerpt) -> str:
    page = "page not available" if excerpt.page is None else f"page {excerpt.page}"
    title = f", {excerpt.source_title}" if excerpt.source_title else ""
    return f'{excerpt.source_id}{title}, {page}: "{excerpt.quote}"'


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="AI Answer Auditor", page_icon="🔎", layout="wide")
    _init_state()

    st.title("AI Answer Auditor")
    st.caption(
        "Paste an answer and the sources that were supposed to support it. "
        "The page splits the answer into claims and quotes the passage that supports or contradicts each one. "
        "The default checker stays on this machine."
    )

    with st.sidebar:
        st.header("Options")
        st.selectbox(
            "Provider",
            PROVIDERS,
            key="provider",
            help="Heuristic runs on this machine. xAI uses XAI_API_KEY from the environment or .env. The key is not shown.",
        )
        if st.session_state.provider == "xai":
            st.warning(
                "xAI sends the answer, the question, and the retrieved passages to the xAI API. "
                "Leave this on heuristic for material that cannot leave this machine. "
                "Quotations are still checked locally."
            )
        st.button("Load example", key="load_example", on_click=_load_example)
        if st.session_state.source_count < MAX_PASTED_SOURCES:
            st.button("Add source", key="add_source", on_click=_add_source)
        else:
            st.caption("Twelve pasted sources is the page limit. Upload files for a larger set.")
        st.caption("An uploaded file is used instead of the text boxes. Load example clears the upload.")

    st.text_input(
        "Question",
        key="question",
        placeholder="Optional. Stored on the report.",
        help="The heuristic checker reads the answer and the sources. The xAI provider also receives this question.",
    )
    st.text_area(
        "Answer",
        key="answer",
        height=160,
        help="The generated answer to check. Text in this box is not opened as a file.",
    )
    uploaded = st.file_uploader(
        "Upload sources",
        type=["txt", "md", "markdown", "pdf", "json"],
        accept_multiple_files=True,
        key=f"uploads-{st.session_state.upload_generation}",
        help="Supported types: .txt, .md, .markdown, .pdf, and .json.",
    )
    if uploaded:
        names = ", ".join(item.name for item in uploaded)
        st.text(f"Audit will read these files instead of the pasted sources: {names}")

    st.subheader("Sources")
    st.caption(
        "A first line that starts with Title: is the document title and is not treated as evidence. "
        "A Markdown heading on the first line is treated the same way."
    )
    for index in range(int(st.session_state.source_count)):
        label = f"Source {index + 1}"
        title_column, remove_column = st.columns([4, 1])
        with title_column:
            st.text_input(
                f"{label} title",
                key=f"source_title_{index}",
                placeholder="Optional title",
            )
        with remove_column:
            if st.session_state.source_count > 1:
                st.button("Remove", key=f"remove_{index}", on_click=_remove_source, args=(index,))
        st.text_area(f"{label} text", key=f"source_text_{index}", height=120)

    if st.button("Audit", type="primary", key="audit"):
        files = [(item.name, item.getvalue()) for item in uploaded] if uploaded else None
        try:
            report, note = audit_request(
                st.session_state.answer,
                st.session_state.question,
                _pasted_from_state(),
                uploads=files,
                provider=st.session_state.provider,
            )
        except AuditorError as exc:
            st.session_state.report = None
            st.session_state.error = str(exc)
            st.session_state.input_note = ""
        else:
            st.session_state.report = report
            st.session_state.error = None
            st.session_state.input_note = note

    if st.session_state.error:
        st.error(st.session_state.error)

    report = st.session_state.report
    if report is None:
        return
    _render_result(report)


def _init_state() -> None:
    import streamlit as st

    if "upload_generation" not in st.session_state:
        st.session_state.upload_generation = 0
    if "answer" not in st.session_state:
        _fill_example(clear_upload=False)
    if "provider" not in st.session_state:
        st.session_state.provider = "heuristic"
    if "report" not in st.session_state:
        st.session_state.report = None
    if "error" not in st.session_state:
        st.session_state.error = None
    if "input_note" not in st.session_state:
        st.session_state.input_note = ""


def _fill_example(*, clear_upload: bool) -> None:
    import streamlit as st

    question, answer, sources = example_inputs()
    st.session_state.question = question
    st.session_state.answer = answer
    st.session_state.source_count = len(sources)
    for index, (title, text) in enumerate(sources):
        st.session_state[f"source_title_{index}"] = title
        st.session_state[f"source_text_{index}"] = text
    if clear_upload:
        st.session_state.upload_generation = int(st.session_state.get("upload_generation", 0)) + 1


def _load_example() -> None:
    import streamlit as st

    _fill_example(clear_upload=True)
    st.session_state.report = None
    st.session_state.error = None
    st.session_state.input_note = ""


def _add_source() -> None:
    import streamlit as st

    count = int(st.session_state.source_count)
    if count >= MAX_PASTED_SOURCES:
        return
    st.session_state[f"source_title_{count}"] = ""
    st.session_state[f"source_text_{count}"] = ""
    st.session_state.source_count = count + 1


def _remove_source(index: int) -> None:
    import streamlit as st

    count = int(st.session_state.source_count)
    if count <= 1 or index < 0 or index >= count:
        return
    for cursor in range(index, count - 1):
        st.session_state[f"source_title_{cursor}"] = st.session_state.get(f"source_title_{cursor + 1}", "")
        st.session_state[f"source_text_{cursor}"] = st.session_state.get(f"source_text_{cursor + 1}", "")
    last = count - 1
    st.session_state.pop(f"source_title_{last}", None)
    st.session_state.pop(f"source_text_{last}", None)
    st.session_state.source_count = count - 1


def _pasted_from_state() -> list[tuple[str, str]]:
    import streamlit as st

    rows: list[tuple[str, str]] = []
    for index in range(int(st.session_state.source_count)):
        rows.append(
            (
                str(st.session_state.get(f"source_title_{index}", "")),
                str(st.session_state.get(f"source_text_{index}", "")),
            )
        )
    return rows


def _render_result(report: AuditReport) -> None:
    import streamlit as st

    st.caption(st.session_state.input_note)
    st.subheader("Summary")
    st.write(report.overall_assessment)
    if report.question:
        st.text(f"Question: {report.question}")
    summary = report.summary
    columns = st.columns(4)
    columns[0].metric("Evidence coverage", coverage_label(summary))
    columns[1].metric("Supported", summary.supported)
    columns[2].metric("Contradicted", summary.contradicted)
    columns[3].metric("Partially supported", summary.partially_supported)
    st.caption(
        f"Factual claims: {summary.factual_claims}. "
        f"Unsupported: {summary.unsupported}. "
        f"Unverifiable: {summary.unverifiable}. "
        "Coverage counts fully supported claims only."
    )

    actions = review_actions(report.claims)
    st.subheader("Review")
    if actions:
        for action in actions:
            st.text(action)
    else:
        st.text("No review actions. Every factual claim is supported by a source excerpt.")

    if report.warnings:
        st.subheader("Warnings")
        for warning in report.warnings:
            st.text(warning)

    claims_tab, sources_tab, report_tab = st.tabs(["Claims", "Sources", "Report"])
    with claims_tab:
        rows = claim_rows(report)
        if rows:
            st.dataframe(rows, hide_index=True, width="stretch")
        else:
            st.info("No claims were extracted.")
        for claim in report.claims:
            _render_claim(claim)
    with sources_tab:
        rows = source_rows(report)
        if rows:
            st.dataframe(rows, hide_index=True, width="stretch")
        else:
            st.info("No sources were loaded.")
    with report_tab:
        markdown = render_markdown(report)
        st.markdown(markdown)
        st.download_button(
            "Download Markdown",
            data=markdown + "\n",
            file_name="audit-report.md",
            mime="text/markdown",
            key="download_md",
        )
        st.download_button(
            "Download JSON",
            data=render_json(report) + "\n",
            file_name="audit-report.json",
            mime="application/json",
            key="download_json",
        )
        st.caption("The downloads are the validated report.")


def _render_claim(claim: ClaimResult) -> None:
    import streamlit as st

    label = f"{claim.claim_id} — {STATUS_LABELS[claim.status]}"
    with st.expander(label):
        st.text(claim.text)
        st.caption(TYPE_LABELS.get(claim.claim_type, claim.claim_type))
        st.text(claim.explanation)
        st.markdown("**Supporting evidence**")
        _render_evidence(claim.supporting_evidence)
        st.markdown("**Contradicting evidence**")
        _render_evidence(claim.contradicting_evidence)
        if claim.verification_notes:
            st.markdown("**Notes**")
            for note in claim.verification_notes:
                st.text(note)


def _render_evidence(excerpts: list[EvidenceExcerpt]) -> None:
    import streamlit as st

    if not excerpts:
        st.text("None")
        return
    for excerpt in excerpts:
        st.text(evidence_line(excerpt))


def _running_as_streamlit_script() -> bool:
    if __name__ == "__main__":
        return True
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
    except ImportError:
        return False
    try:
        return get_script_run_ctx(suppress_warning=True) is not None
    except TypeError:
        return get_script_run_ctx() is not None


if _running_as_streamlit_script():
    main()
