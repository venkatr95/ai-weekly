"""Web UI for the evidence-only research agent. Run with: streamlit run streamlit_app.py"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_SRC = ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from evidence_agent.config import Settings
from evidence_agent.errors import ConfigurationError, EvidenceAgentError
from evidence_agent.ingestion import SUPPORTED_SUFFIXES
from evidence_agent.pipeline import ResearchPipeline
from evidence_agent.rendering import render_markdown
from evidence_agent.schemas import AnswerResponse, Citation, DocumentRecord, IndexReport, RetrievedPassage
from evidence_agent.security import scrub_text

PROVIDERS = ("extractive", "xai", "openai_compatible")
EXAMPLE_IDS = ("q_definition", "q_partial", "q_unanswerable", "q_conflict")
EXAMPLE_DOCUMENTS = ROOT / "examples" / "documents"
STATUS_LABELS = {
    "supported": "Supported",
    "interpretation": "Interpretation",
    "unsupported": "Unsupported",
}
VERIFICATION_LABELS = {
    "verified": "Verified",
    "rejected": "Rejected",
    "unverified": "Unverified",
}
_UNSAFE_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_SETTINGS_LOCK = threading.Lock()


def example_questions() -> list[str]:
    """Questions from the bundled gold set, in demo order."""

    payload = json.loads((ROOT / "examples" / "questions.json").read_text(encoding="utf-8"))
    by_id = {item["id"]: item["question"] for item in payload}
    return [by_id[item_id] for item_id in EXAMPLE_IDS]


def new_work_dirs() -> tuple[Path, Path]:
    """Session index and upload folder. Neither path is data/index."""

    return (
        Path(tempfile.mkdtemp(prefix="evidence-webui-index-")),
        Path(tempfile.mkdtemp(prefix="evidence-webui-docs-")),
    )


def build_settings(index_dir: Path, provider: str) -> Settings:
    """Settings for one page action.

    The selected provider replaces GENERATION_PROVIDER for this call. Embeddings
    stay local, so indexing does not send document text to an embedding API.
    The process environment is restored before this returns.
    """

    if provider not in PROVIDERS:
        raise ConfigurationError(
            "The page provider must be extractive, xai, or openai_compatible. "
            f"Received {provider!r}."
        )
    with _SETTINGS_LOCK:
        previous = {
            "GENERATION_PROVIDER": os.environ.get("GENERATION_PROVIDER"),
            "EMBEDDING_PROVIDER": os.environ.get("EMBEDDING_PROVIDER"),
        }
        os.environ["GENERATION_PROVIDER"] = provider
        os.environ["EMBEDDING_PROVIDER"] = "local"
        try:
            settings = Settings.load()
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    settings.index_dir = Path(index_dir)
    settings.generation_provider = provider
    settings.embedding_provider = "local"
    return settings


def public_error(exc: EvidenceAgentError, index_dir: Path) -> str:
    """Error text with secrets and token-like strings removed."""

    try:
        settings = build_settings(index_dir, "extractive")
    except EvidenceAgentError:
        return scrub_text(str(exc))
    secrets = [settings.xai_api_key, settings.embedding_api_key, settings.openai_compatible_api_key]
    return scrub_text(str(exc), secrets)


def index_directory(
    path: Path,
    *,
    index_dir: Path,
    provider: str = "extractive",
    rebuild: bool = True,
) -> IndexReport:
    settings = build_settings(index_dir, provider)
    return ResearchPipeline(settings).index_path(Path(path), rebuild=rebuild)


def describe_index(report: IndexReport, source_label: str) -> str:
    stats = report.stats
    return (
        f"Indexed {stats.files_indexed} documents ({stats.chunks} chunks) from {source_label}. "
        f"Reused {stats.files_reused}. Skipped {stats.files_skipped}. "
        f"Empty {stats.files_empty}. OCR required {stats.files_needs_ocr}. Failed {stats.files_failed}."
    )


def safe_upload_name(name: str, index: int, used: set[str]) -> str:
    """Basename only. A path in the upload name is not opened."""

    base = Path(str(name).replace("\\", "/")).name
    if not base or base in {".", ".."}:
        raise ConfigurationError(f"Uploaded file {index} has no file name.")
    suffix = Path(base).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ConfigurationError(
            f"Unsupported source type '{suffix or base}'. "
            "Supported types: .pdf, .txt, .md, .markdown."
        )
    stem = _UNSAFE_NAME.sub("_", Path(base).stem).strip(" .") or f"document-{index}"
    stem = stem[:80]
    candidate = f"{stem}{suffix}"
    counter = 2
    while candidate.lower() in used:
        candidate = f"{stem}-{counter}{suffix}"
        counter += 1
    used.add(candidate.lower())
    return candidate


def write_uploads(files: list[tuple[str, bytes]], directory: Path) -> list[str]:
    """Replace the upload folder with these files and return the safe names."""

    if not files:
        raise ConfigurationError("Provide at least one PDF, Markdown, or text file.")
    directory.mkdir(parents=True, exist_ok=True)
    resolved = directory.resolve()
    if (resolved / "manifest.json").is_file() or (resolved / "embeddings.npy").is_file():
        raise ConfigurationError("Refusing to write uploads into an index directory.")
    for child in list(resolved.iterdir()):
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
    names: list[str] = []
    used: set[str] = set()
    for index, (name, data) in enumerate(files, start=1):
        if not isinstance(data, (bytes, bytearray)):
            raise ConfigurationError(f"Could not read '{name}': the upload is not a file.")
        safe = safe_upload_name(str(name), index, used)
        path = resolved / safe
        if path.parent != resolved:
            raise ConfigurationError(f"Uploaded file {index} has no file name.")
        path.write_bytes(bytes(data))
        names.append(safe)
    return names


def index_uploads(
    files: list[tuple[str, bytes]],
    *,
    index_dir: Path,
    corpus_dir: Path,
    provider: str = "extractive",
    rebuild: bool = True,
) -> tuple[IndexReport, str]:
    names = write_uploads(files, corpus_dir)
    report = index_directory(corpus_dir, index_dir=index_dir, provider=provider, rebuild=rebuild)
    if len(names) == 1:
        label = f"the uploaded file {names[0]}"
    else:
        label = "the uploaded files " + ", ".join(names)
    return report, describe_index(report, label)


def folder_path(value: str) -> Path:
    stripped = value.strip().strip('"').strip("'")
    if not stripped:
        raise ConfigurationError("Enter a folder or a supported file.")
    return Path(stripped)


def _whole_k(k: int | float | None) -> int | None:
    if k is None:
        return None
    if isinstance(k, bool) or not isinstance(k, (int, float)):
        raise ConfigurationError("Passages to retrieve must be at least 1.")
    if isinstance(k, float) and not k.is_integer():
        raise ConfigurationError("Passages to retrieve must be a whole number.")
    whole = int(k)
    if whole < 1:
        raise ConfigurationError("Passages to retrieve must be at least 1.")
    return whole


def _threshold(threshold: float | None) -> float | None:
    if threshold is None:
        return None
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise ConfigurationError("Minimum score must be between 0 and 1.")
    if not 0 <= float(threshold) <= 1:
        raise ConfigurationError("Minimum score must be between 0 and 1.")
    return float(threshold)


def ask_question(
    question: str,
    *,
    index_dir: Path,
    provider: str = "extractive",
    k: int | float | None = None,
    threshold: float | None = None,
) -> tuple[AnswerResponse, list[RetrievedPassage]]:
    """Ask one question. The question string is not opened as a path."""

    settings = build_settings(index_dir, provider)
    return ResearchPipeline(settings).ask(question, k=_whole_k(k), threshold=_threshold(threshold))


def claim_rows(response: AnswerResponse) -> list[dict[str, str]]:
    citations = {citation.id: citation for citation in response.citations}
    rows: list[dict[str, str]] = []
    for claim in response.claims:
        sources: list[str] = []
        for citation_id in claim.citation_ids:
            citation = citations.get(citation_id)
            if citation is None:
                sources.append("missing citation")
                continue
            page = "" if citation.page is None else f", page {citation.page}"
            sources.append(f"{citation.source_path}{page}")
        rows.append(
            {
                "Claim": claim.id,
                "Status": STATUS_LABELS.get(claim.evidence_status, claim.evidence_status),
                "Verification": VERIFICATION_LABELS.get(claim.verification_status, claim.verification_status),
                "Sources": "; ".join(sources),
                "Finding": claim.text,
            }
        )
    return rows


def source_rows(documents: list[DocumentRecord]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for document in documents:
        if document.error:
            status = document.error
        elif document.warning:
            status = document.warning
        else:
            status = "ok"
        pages = "-" if document.page_count is None else str(document.page_count)
        rows.append(
            {
                "Path": document.relative_path,
                "Type": document.file_type,
                "Pages": pages,
                "Chunks": str(len(document.chunk_ids)),
                "OCR": "yes" if document.needs_ocr else "no",
                "Status": status,
            }
        )
    return rows


def passage_rows(passages: list[RetrievedPassage]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for passage in passages:
        pages = "-" if passage.page_start is None else f"{passage.page_start}-{passage.page_end}"
        rows.append(
            {
                "Source": passage.relative_path,
                "Pages": pages,
                "Score": f"{passage.score:.3f}",
                "Chunk": passage.chunk_id,
            }
        )
    return rows


def citation_line(citation: Citation) -> str:
    page = "page not available" if citation.page is None else f"page {citation.page}"
    return f"{citation.source_path}, {page} ({citation.chunk_id})"


def chunk_text(index_dir: Path, chunk_id: str, provider: str = "extractive") -> str:
    store = ResearchPipeline(build_settings(index_dir, provider)).open_index()
    chunk = store.chunks_by_id().get(chunk_id)
    if chunk is None:
        raise ConfigurationError(
            f"No chunk with id {chunk_id!r} is in the index. Run: python cli.py sources"
        )
    return chunk.text


def render_json(response: AnswerResponse) -> str:
    return json.dumps(response.model_dump(), ensure_ascii=False, indent=2)


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="Evidence-only research agent", page_icon="📄", layout="wide")
    _init_state()

    st.title("Evidence-only research agent")
    st.caption(
        "Index PDF, Markdown, and text files, then ask a question. "
        "Every finding quotes a stored passage, or the page says the documents do not support it. "
        "The default provider stays on this machine. This session does not change data/index."
    )

    _sidebar()
    _documents()
    st.text_area(
        "Question",
        key="question",
        height=120,
        help="Asked against the session index. Text in this box is not opened as a file.",
    )
    if st.button("Ask", type="primary", key="ask"):
        _ask()

    if st.session_state.error:
        st.error(st.session_state.error)
    _render_index()
    if st.session_state.response is not None:
        _render_answer()


def _init_state() -> None:
    import streamlit as st

    if "index_dir" not in st.session_state or "corpus_dir" not in st.session_state:
        index_dir, corpus_dir = new_work_dirs()
        st.session_state.index_dir = str(index_dir)
        st.session_state.corpus_dir = str(corpus_dir)
    questions = example_questions()
    if "provider" not in st.session_state:
        st.session_state.provider = "extractive"
    if "k" not in st.session_state:
        st.session_state.k = 6
    if "threshold" not in st.session_state:
        st.session_state.threshold = 0.15
    if "rebuild" not in st.session_state:
        st.session_state.rebuild = True
    if "example_question" not in st.session_state:
        st.session_state.example_question = questions[0]
    if "question" not in st.session_state:
        st.session_state.question = questions[0]
    if "folder_path" not in st.session_state:
        st.session_state.folder_path = ""
    if "index_report" not in st.session_state:
        st.session_state.index_report = None
    if "response" not in st.session_state:
        st.session_state.response = None
    if "passages" not in st.session_state:
        st.session_state.passages = None
    if "error" not in st.session_state:
        st.session_state.error = None
    if "input_note" not in st.session_state:
        st.session_state.input_note = ""


def _sidebar() -> None:
    import streamlit as st

    with st.sidebar:
        st.header("Options")
        st.selectbox(
            "Provider",
            PROVIDERS,
            key="provider",
            help=(
                "Extractive quotes indexed sentences on this machine. "
                "xAI and openai_compatible send the question and the retrieved passages to a model. "
                "Embeddings stay local. The API key is not shown."
            ),
        )
        _provider_warning()
        st.number_input(
            "Passages",
            min_value=1,
            max_value=50,
            step=1,
            key="k",
            help="How many passages to retrieve. The score only ranks them.",
        )
        st.number_input(
            "Minimum score",
            min_value=0.0,
            max_value=1.0,
            step=0.05,
            format="%.2f",
            key="threshold",
            help="Passages below this hybrid score are dropped. The score is not evidence.",
        )
        st.checkbox(
            "Replace the current index",
            key="rebuild",
            help="On: throw away the session index, then read the files. Off: reuse unchanged files.",
        )
        st.header("Example question")
        st.selectbox("Sample", example_questions(), key="example_question")
        st.button("Use sample question", key="use_example", on_click=_use_example_question)
        with st.expander("Session index"):
            st.text(st.session_state.index_dir)
            st.caption("This folder is temporary. It is not data/index. Indexing here does not change the CLI index.")


def _provider_warning() -> None:
    import streamlit as st

    provider = st.session_state.provider
    if provider == "extractive":
        return
    if provider == "xai":
        destination = "the xAI API"
    else:
        destination = "OPENAI_COMPATIBLE_BASE_URL"
    st.warning(
        f"{provider} sends the question and the retrieved passages to {destination}. "
        "Leave this on extractive for material that cannot leave this machine. "
        "Citations are still checked locally. The API key is not shown."
    )


def _use_example_question() -> None:
    import streamlit as st

    st.session_state.question = st.session_state.example_question
    st.session_state.response = None
    st.session_state.passages = None
    st.session_state.error = None


def _documents() -> None:
    import streamlit as st

    st.subheader("Documents")
    st.caption(
        "Supported types: .pdf, .txt, .md, and .markdown. "
        "A scanned PDF is reported and is not OCR'd. "
        "Hidden files are ignored. An uploaded name is only a file name. It is not opened as a path."
    )
    st.file_uploader(
        "Upload files",
        type=[suffix.lstrip(".") for suffix in sorted(SUPPORTED_SUFFIXES)],
        accept_multiple_files=True,
        key="uploads",
        help="These files replace the session upload folder, then the session index is built from that folder.",
    )
    st.text_input(
        "Folder or file on this machine",
        key="folder_path",
        placeholder="examples/documents",
        help="Index reads this path on this machine, the same way the CLI does.",
    )
    example_column, upload_column, folder_column = st.columns(3)
    with example_column:
        if st.button("Index example corpus", key="index_example"):
            _index_example()
    with upload_column:
        if st.button("Index uploaded files", key="index_uploads"):
            _index_uploaded()
    with folder_column:
        if st.button("Index folder", key="index_folder"):
            _index_folder()


def _index_example() -> None:
    import streamlit as st

    _index_call(
        lambda: index_directory(
            EXAMPLE_DOCUMENTS,
            index_dir=Path(st.session_state.index_dir),
            provider=st.session_state.provider,
            rebuild=bool(st.session_state.rebuild),
        ),
        "examples/documents",
    )


def _index_uploaded() -> None:
    import streamlit as st

    uploaded = st.session_state.get("uploads")
    if not uploaded:
        files: list[tuple[str, bytes]] = []
    elif isinstance(uploaded, list):
        files = [(item.name, item.getvalue()) for item in uploaded]
    else:
        files = [(uploaded.name, uploaded.getvalue())]

    def run() -> tuple[IndexReport, str]:
        return index_uploads(
            files,
            index_dir=Path(st.session_state.index_dir),
            corpus_dir=Path(st.session_state.corpus_dir),
            provider=st.session_state.provider,
            rebuild=bool(st.session_state.rebuild),
        )

    _index_call(run, None)


def _index_folder() -> None:
    import streamlit as st

    try:
        path = folder_path(str(st.session_state.folder_path))
    except EvidenceAgentError as exc:
        st.session_state.error = public_error(exc, Path(st.session_state.index_dir))
        return
    _index_call(
        lambda: index_directory(
            path,
            index_dir=Path(st.session_state.index_dir),
            provider=st.session_state.provider,
            rebuild=bool(st.session_state.rebuild),
        ),
        str(path),
    )


def _index_call(run, source_label: str | None) -> None:
    import streamlit as st

    try:
        result = run()
    except EvidenceAgentError as exc:
        st.session_state.error = public_error(exc, Path(st.session_state.index_dir))
        return
    if isinstance(result, tuple):
        report, note = result
    else:
        report = result
        note = describe_index(report, source_label or "the selected files")
    st.session_state.index_report = report
    st.session_state.input_note = note
    st.session_state.response = None
    st.session_state.passages = None
    st.session_state.error = None
    st.session_state.pop("chunk_id", None)


def _ask() -> None:
    import streamlit as st

    try:
        response, passages = ask_question(
            str(st.session_state.question),
            index_dir=Path(st.session_state.index_dir),
            provider=st.session_state.provider,
            k=st.session_state.k,
            threshold=float(st.session_state.threshold),
        )
    except EvidenceAgentError as exc:
        st.session_state.response = None
        st.session_state.passages = None
        st.session_state.error = public_error(exc, Path(st.session_state.index_dir))
        return
    st.session_state.response = response
    st.session_state.passages = passages
    st.session_state.error = None


def _render_index() -> None:
    import streamlit as st

    report = st.session_state.index_report
    if report is None:
        return
    if st.session_state.input_note:
        st.caption(st.session_state.input_note)
    stats = report.stats
    columns = st.columns(4)
    columns[0].metric("Documents", stats.files_indexed)
    columns[1].metric("Chunks", stats.chunks)
    columns[2].metric("Needs OCR", stats.files_needs_ocr)
    columns[3].metric("Failed", stats.files_failed)
    st.caption(
        f"Embedding: {report.embedding_provider} ({report.embedding_dimensions} dimensions). "
        "A retrieval score is not evidence."
    )
    for warning in report.ocr_warnings:
        st.warning(warning)
    for error in report.errors:
        st.error(error)
    if stats.files_indexed == 0:
        st.warning("No searchable documents were indexed.")


def _render_answer() -> None:
    import streamlit as st

    response = st.session_state.response
    passages = st.session_state.passages or []
    st.subheader("Answer")
    st.text(response.answer)
    columns = st.columns(4)
    columns[0].metric("Abstained", "Yes" if response.abstained else "No")
    columns[1].metric("Findings", len(response.claims))
    columns[2].metric("Conflicts", len(response.conflicts))
    columns[3].metric("Passages", response.passages_retrieved)
    st.caption(f"Provider: {response.provider}. Passages retrieved: {response.passages_retrieved}.")

    findings_tab, passages_tab, sources_tab, report_tab = st.tabs(
        ["Findings", "Passages", "Sources", "Report"]
    )
    with findings_tab:
        _render_findings(response)
    with passages_tab:
        _render_passages(passages)
    with sources_tab:
        _render_sources()
    with report_tab:
        _render_report(response)


def _render_findings(response: AnswerResponse) -> None:
    import streamlit as st

    rows = claim_rows(response)
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")
    else:
        st.info("No findings were verified.")
    citations = {citation.id: citation for citation in response.citations}
    for claim in response.claims:
        label = f"{claim.id} — {STATUS_LABELS.get(claim.evidence_status, claim.evidence_status)}"
        with st.expander(label):
            st.text(claim.text)
            st.caption(VERIFICATION_LABELS.get(claim.verification_status, claim.verification_status))
            for citation_id in claim.citation_ids:
                citation = citations.get(citation_id)
                if citation is None:
                    st.text("Missing citation")
                    continue
                st.text(citation_line(citation))
                st.text(citation.excerpt)

    st.subheader("Unanswered questions")
    if response.unanswered_questions:
        for item in response.unanswered_questions:
            st.text(item.question)
            st.caption(f"{item.reason}: {item.detail}")
    else:
        st.text("None.")

    st.subheader("Conflicts")
    if response.conflicts:
        for index, conflict in enumerate(response.conflicts, start=1):
            state = "resolved" if conflict.resolved else "unresolved"
            st.text(f"{index}. {conflict.topic} ({state})")
            st.caption(conflict.note)
            for position in conflict.positions:
                st.text(position.summary)
                for citation_id in position.citation_ids:
                    citation = citations.get(citation_id)
                    if citation is not None:
                        st.text(citation_line(citation))
                        st.text(citation.excerpt)
    else:
        st.text("None.")

    st.subheader("Limitations")
    if response.limitations:
        for note in response.limitations:
            st.text(note)
    else:
        st.text("None.")


def _render_passages(passages: list[RetrievedPassage]) -> None:
    import streamlit as st

    st.caption("Retrieved passages rank candidates. A score is not evidence.")
    rows = passage_rows(passages)
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")
    else:
        st.info("No passages were retrieved.")
    for index, passage in enumerate(passages, start=1):
        pages = "-" if passage.page_start is None else f"{passage.page_start}-{passage.page_end}"
        st.text(
            f"{index}. {passage.relative_path} pages {pages} "
            f"score={passage.score:.3f} cosine={passage.cosine:.3f} lexical={passage.lexical:.3f} "
            f"chunk={passage.chunk_id}"
        )
        st.text(passage.text)


def _render_sources() -> None:
    import streamlit as st

    try:
        store = ResearchPipeline(build_settings(Path(st.session_state.index_dir), "extractive")).open_index()
    except EvidenceAgentError as exc:
        st.info(public_error(exc, Path(st.session_state.index_dir)))
        return
    rows = source_rows(store.documents)
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")
    else:
        st.info("The index has no documents.")
    chunks = list(store.chunks)
    if not chunks:
        st.info("The index has no chunks.")
        return
    chunk_ids = [chunk.chunk_id for chunk in chunks]
    if st.session_state.get("chunk_id") not in chunk_ids:
        st.session_state.chunk_id = chunk_ids[0]
    selected = st.selectbox("Chunk", chunk_ids, key="chunk_id")
    chunk = store.chunks_by_id()[selected]
    pages = "-" if chunk.page_start is None else f"{chunk.page_start}-{chunk.page_end}"
    st.caption(f"{chunk.relative_path} pages {pages}")
    st.text(chunk.text)


def _render_report(response: AnswerResponse) -> None:
    import streamlit as st

    markdown = render_markdown(response)
    st.markdown(markdown)
    st.download_button(
        "Download Markdown",
        data=markdown,
        file_name="answer.md",
        mime="text/markdown",
        key="download_md",
    )
    st.download_button(
        "Download JSON",
        data=render_json(response) + "\n",
        file_name="answer.json",
        mime="application/json",
        key="download_json",
    )
    st.caption("The downloads are the verified answer. Passage scores are not included.")


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
