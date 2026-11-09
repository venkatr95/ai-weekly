"""Web UI for the RAG agent. Run with: py -m streamlit run streamlit_app.py"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from app.config import Settings, make_settings
from app.errors import RAGError, GenerationError
from app.generation.answer_generator import build_generator
from app.ingestion.parser import MARKDOWN, PDF, content_type_for_filename
from app.pipeline import RAGPipeline, build_pipeline
from app.sample_pdf import build_refund_policy_pdf
from app.schemas.answer import INSUFFICIENT_ANSWER, RAGResponse, RetrievedChunk

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / "evaluation" / "corpus"
SAMPLE_PDF = ROOT / "sample_docs" / "refund-policy.pdf"
ANSWERERS = ("extractive", "xai")
EXAMPLE_QUESTIONS = (
    "What is the refund period?",
    "What is the difference between the refund policy and the cancellation policy?",
    "How many weeks of paid parental leave do employees receive?",
    "What is the company's annual revenue?",
)
SUPPORTED_EXTENSIONS = (".pdf", ".txt", ".md", ".markdown")
MAX_HISTORY = 20
_UNSAFE_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_TOKEN = re.compile(r"\b(?:sk-|xai-)[A-Za-z0-9_\-]{8,}\b")
TYPE_LABELS = {
    "application/pdf": "pdf",
    "text/plain": "txt",
    "text/markdown": "markdown",
}


class WebUIError(Exception):
    """A problem the page can show without a traceback."""


@dataclass(frozen=True)
class PreparedUpload:
    filename: str
    data: bytes
    content_type: str


@dataclass(frozen=True)
class IndexedFile:
    document_id: str
    filename: str
    content_type: str
    status: str
    chunks: int


@dataclass(frozen=True)
class IngestBatch:
    indexed: list[IndexedFile]
    errors: list[str]


def new_pipeline() -> RAGPipeline:
    """In-memory index and the extractive answerer.

    `make_settings` ignores the process environment, so a `VECTOR_STORE=postgres`
    value in the shell does not make the page open a database.
    """

    settings = make_settings(
        database_url="postgresql+psycopg://rag:rag@localhost:5432/rag",
        vector_store="memory",
        xai_api_key=None,
        xai_base_url="https://api.x.ai/v1",
        llm_model="grok-4.7",
        llm_provider="extractive",
        reasoning_effort="low",
        embedding_provider="hashing",
        embedding_model="embed-latest",
        embedding_dim=384,
        chunk_size_tokens=500,
        chunk_overlap_tokens=100,
        top_k=5,
        min_score=None,
        vector_weight=None,
        rerank_pool_multiplier=6,
        max_upload_bytes=20 * 1024 * 1024,
        log_level="INFO",
    )
    return build_pipeline(settings)


def set_answerer(pipeline: RAGPipeline, provider: str) -> str:
    """Swap the answerer. The index and the hashing embedder stay in place."""

    if provider not in ANSWERERS:
        raise WebUIError(f"The answerer must be extractive or xai. Received {provider!r}.")
    settings = _answerer_settings(pipeline, provider)
    try:
        generator = build_generator(settings)
    except GenerationError as exc:
        if "XAI_API_KEY" in str(exc):
            raise WebUIError(
                "xAI answers need XAI_API_KEY in the environment. "
                "The extractive answerer runs on this machine without a key."
            ) from exc
        raise WebUIError(public_error(exc)) from exc
    pipeline.settings = settings
    pipeline.generator = generator
    return generator.name


def ask(
    pipeline: RAGPipeline,
    question: str,
    *,
    top_k: int | float | None = None,
    debug: bool = False,
    document_count: int | None = None,
) -> RAGResponse:
    """Ask one question. The question string is not opened as a path."""

    text = question.strip()
    if not text:
        raise WebUIError("Enter a question about the indexed documents.")
    if len(text) > 4000:
        raise WebUIError("A question can be at most 4000 characters.")
    if document_count == 0:
        raise WebUIError("Index at least one document before asking.")
    try:
        return pipeline.answer(text, top_k=_whole_top_k(top_k), debug=debug)
    except WebUIError:
        raise
    except (RAGError, ValueError) as exc:
        raise WebUIError(public_error(exc, pipeline.settings.resolved_api_key())) from exc


def sample_files(corpus: Path | None = None, pdf: Path | None = None) -> list[PreparedUpload]:
    """Bundled policies plus the refund-policy PDF. Paths are not stored as names."""

    corpus_dir = CORPUS if corpus is None else corpus
    pdf_path = SAMPLE_PDF if pdf is None else pdf
    if not corpus_dir.is_dir():
        raise WebUIError("The sample corpus is missing.")
    prepared: list[PreparedUpload] = []
    for path in sorted(corpus_dir.glob("*.md")):
        prepared.append(PreparedUpload(path.name, path.read_bytes(), MARKDOWN))
    if pdf_path.is_file():
        pdf_bytes = pdf_path.read_bytes()
    else:
        pdf_bytes = build_refund_policy_pdf()
    prepared.append(PreparedUpload("refund-policy.pdf", pdf_bytes, PDF))
    if not prepared:
        raise WebUIError("The sample corpus is empty.")
    return prepared


def prepare_uploads(
    files: list[tuple[str, bytes]],
    *,
    max_bytes: int = 20 * 1024 * 1024,
) -> list[PreparedUpload]:
    """Check names, sizes, and types before anything is indexed."""

    if not files:
        raise WebUIError("Choose at least one PDF, TXT, or Markdown file.")
    prepared: list[PreparedUpload] = []
    used: set[str] = set()
    for index, (name, data) in enumerate(files, start=1):
        if not isinstance(data, (bytes, bytearray)):
            raise WebUIError(f"Could not read '{name}'. The upload is not a file.")
        filename = safe_upload_name(str(name), index, used)
        payload = bytes(data)
        if not payload:
            raise WebUIError(f"'{filename}' is empty.")
        if len(payload) > max_bytes:
            raise WebUIError(f"'{filename}' exceeds the {_size_label(max_bytes)} upload limit.")
        try:
            content_type = content_type_for_filename(filename)
        except RAGError as exc:
            raise WebUIError(public_error(exc)) from exc
        prepared.append(PreparedUpload(filename, payload, content_type))
    return prepared


def ingest_prepared(pipeline: RAGPipeline, prepared: list[PreparedUpload]) -> IngestBatch:
    """Index each prepared file. One bad file does not remove the ones already stored."""

    indexed: list[IndexedFile] = []
    errors: list[str] = []
    for item in prepared:
        try:
            response = pipeline.ingest(item.filename, item.data, item.content_type)
        except RAGError as exc:
            errors.append(f"{item.filename}: {public_error(exc)}")
            continue
        indexed.append(
            IndexedFile(
                document_id=response.document_id,
                filename=item.filename,
                content_type=item.content_type,
                status=response.status,
                chunks=response.chunks,
            )
        )
    return IngestBatch(indexed=indexed, errors=errors)


def describe_ingest(batch: IngestBatch) -> str:
    """One line for the last index action. File names only, no directories."""

    chunks = sum(item.chunks for item in batch.indexed)
    if len(batch.indexed) == 1:
        label = batch.indexed[0].filename
    elif batch.indexed:
        label = ", ".join(item.filename for item in batch.indexed)
    else:
        label = "no files"
    text = f"Indexed {len(batch.indexed)} documents ({chunks} chunks): {label}."
    if batch.errors:
        text += f" Failed {len(batch.errors)}."
    return text


def document_rows(documents: list[IndexedFile]) -> list[dict[str, str]]:
    return [
        {
            "Document": item.filename,
            "Type": TYPE_LABELS.get(item.content_type, item.content_type),
            "Chunks": str(item.chunks),
            "Status": item.status,
            "Id": item.document_id,
        }
        for item in documents
    ]


def citation_rows(response: RAGResponse) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for citation in response.citations:
        page = "-" if citation.page is None else str(citation.page)
        rows.append(
            {
                "Id": str(citation.id),
                "Document": citation.document,
                "Page": page,
                "Chunk": citation.chunk_id,
            }
        )
    return rows


def retrieved_rows(response: RAGResponse) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for chunk in response.retrieved or []:
        page = "-" if chunk.page is None else str(chunk.page)
        rows.append(
            {
                "Document": chunk.filename,
                "Page": page,
                "Score": f"{chunk.score:.3f}",
                "Chunk": chunk.chunk_id,
            }
        )
    return rows


def citation_line(citation) -> str:
    page = "n/a" if citation.page is None else str(citation.page)
    return f"[{citation.id}] {citation.document}, page {page}, {citation.chunk_id}"


def retrieved_caption(chunk: RetrievedChunk) -> str:
    page = "n/a" if chunk.page is None else str(chunk.page)
    text = f"{chunk.filename}, page {page}, score {chunk.score:.3f}"
    if chunk.vector_score is not None:
        text += f", vector {chunk.vector_score:.3f}"
    return f"{text}, {chunk.chunk_id}"


def render_answer_text(response: RAGResponse) -> str:
    lines = [response.answer, ""]
    if response.citations:
        lines.extend(citation_line(citation) for citation in response.citations)
    else:
        lines.append("(no citations)")
    return "\n".join(lines) + "\n"


def render_json(response: RAGResponse) -> str:
    payload = response.model_dump()
    if payload.get("retrieved") is None:
        payload.pop("retrieved", None)
    return json.dumps(payload, ensure_ascii=False, indent=2)


def status_line(pipeline: RAGPipeline, documents: list[IndexedFile]) -> str:
    """Session status. The API key and the database URL are left out."""

    chunks = sum(item.chunks for item in documents)
    text = (
        f"Index: in memory. Embeddings: {pipeline.embedder.name}. "
        f"Answerer: {pipeline.generator.name}. "
        f"Documents: {len(documents)}. Chunks: {chunks}."
    )
    return _scrub(text, pipeline.settings.resolved_api_key())


def public_error(exc: BaseException, *secrets: str | None) -> str:
    """Error text with configured API keys and token-like strings removed."""

    text = str(exc).strip() or exc.__class__.__name__
    return _scrub(text, *secrets)


def safe_upload_name(name: str, index: int, used: set[str]) -> str:
    """Basename only. A path in the upload name is not opened."""

    base = Path(str(name).replace("\\", "/")).name
    if not base or base in {".", ".."}:
        raise WebUIError(f"Uploaded file {index} has no file name.")
    suffix = Path(base).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        shown = suffix or base
        raise WebUIError(
            f"Unsupported document type '{shown}'. Supported types: .pdf, .txt, .md, .markdown."
        )
    stem = _UNSAFE_NAME.sub("_", Path(base).stem).strip(" .") or f"document-{index}"
    stem = stem[:80]
    candidate = f"{stem}{suffix}"
    counter = 2
    while candidate.casefold() in used:
        candidate = f"{stem}-{counter}{suffix}"
        counter += 1
    used.add(candidate.casefold())
    return candidate


def _answerer_settings(pipeline: RAGPipeline, provider: str) -> Settings:
    data = pipeline.settings.model_dump()
    data["llm_provider"] = provider
    data["xai_api_key"] = _env("XAI_API_KEY") if provider == "xai" else None
    data["xai_base_url"] = _env("XAI_BASE_URL") or pipeline.settings.xai_base_url
    data["llm_model"] = _env("LLM_MODEL") or pipeline.settings.llm_model
    effort = _env("REASONING_EFFORT")
    if effort:
        data["reasoning_effort"] = effort
    try:
        return Settings.model_validate(data)
    except ValidationError as exc:
        raise WebUIError(
            "Answerer settings are invalid. Check REASONING_EFFORT and LLM_MODEL."
        ) from exc


def _env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def _whole_top_k(top_k: int | float | None) -> int | None:
    if top_k is None:
        return None
    if isinstance(top_k, bool) or not isinstance(top_k, (int, float)):
        raise WebUIError("Passages to retrieve must be a whole number from 1 to 20.")
    if isinstance(top_k, float) and not top_k.is_integer():
        raise WebUIError("Passages to retrieve must be a whole number from 1 to 20.")
    whole = int(top_k)
    if whole < 1 or whole > 20:
        raise WebUIError("Passages to retrieve must be a whole number from 1 to 20.")
    return whole


def _size_label(max_bytes: int) -> str:
    megabytes = max_bytes / (1024 * 1024)
    if megabytes >= 1 and max_bytes % (1024 * 1024) == 0:
        return f"{int(megabytes)} MB"
    return f"{max_bytes} bytes"


def _scrub(text: str, *secrets: str | None) -> str:
    for secret in (*secrets, os.environ.get("XAI_API_KEY")):
        if secret and len(secret) >= 8:
            text = text.replace(secret, "[redacted]")
    text = _TOKEN.sub("[redacted]", text)
    if len(text) > 500:
        text = text[:500] + "..."
    return text


def _file_payloads(uploaded) -> list[tuple[str, bytes]]:
    if not uploaded:
        return []
    items = uploaded if isinstance(uploaded, list) else [uploaded]
    return [(item.name, item.getvalue()) for item in items]


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="RAG Agent", page_icon="📄", layout="wide")
    _init_state()

    st.title("RAG Agent")
    st.caption(
        "Index PDF, TXT, and Markdown, then ask a question. "
        "Each answer cites retrieved chunks. "
        "When the documents do not support the question, the answer says so and cites nothing. "
        "Embeddings stay on this machine. This browser session keeps the index in memory."
    )

    _sidebar()
    _documents()
    st.text_area(
        "Question",
        key="question",
        height=120,
        max_chars=4000,
        help="Asked against the session index. Text in this box is not opened as a file.",
    )
    if st.button("Ask", type="primary", key="ask"):
        _ask()
    _render_feedback()
    _render_answer()


def _init_state() -> None:
    import streamlit as st

    if st.session_state.get("pipeline") is None:
        st.session_state.pipeline = new_pipeline()
    if "documents" not in st.session_state:
        st.session_state.documents = []
    if "provider" not in st.session_state:
        st.session_state.provider = "extractive"
    if "top_k" not in st.session_state:
        st.session_state.top_k = 5
    if "show_retrieved" not in st.session_state:
        st.session_state.show_retrieved = True
    if "example_question" not in st.session_state:
        st.session_state.example_question = EXAMPLE_QUESTIONS[0]
    if "question" not in st.session_state:
        st.session_state.question = EXAMPLE_QUESTIONS[0]
    if "response" not in st.session_state:
        st.session_state.response = None
    if "history" not in st.session_state:
        st.session_state.history = []
    if "error" not in st.session_state:
        st.session_state.error = None
    if "note" not in st.session_state:
        st.session_state.note = ""
    if "upload_generation" not in st.session_state:
        st.session_state.upload_generation = 0


def _sidebar() -> None:
    import streamlit as st

    with st.sidebar:
        st.header("Answer")
        st.selectbox(
            "Answerer",
            ANSWERERS,
            key="provider",
            help=(
                "Extractive quotes retrieved sentences on this machine. "
                "xAI sends the question and the retrieved chunks to grok-4.7. "
                "The index is kept either way. The API key is not shown."
            ),
        )
        if st.session_state.provider == "xai":
            st.warning(
                "xAI sends the question and the retrieved chunks to grok-4.7. "
                "Citations are still checked on this machine. The API key stays off this page."
            )
        st.number_input(
            "Passages",
            min_value=1,
            max_value=20,
            step=1,
            key="top_k",
            help="How many chunks to send to the answerer after reranking.",
        )
        st.checkbox(
            "Show retrieved chunks",
            key="show_retrieved",
            help="Include the chunks and scores returned for this question.",
        )
        st.header("Sample question")
        st.selectbox("Sample", EXAMPLE_QUESTIONS, key="example_question")
        st.caption("These questions refer to the bundled policies and handbook.")
        st.button("Use sample question", key="use_example", on_click=_use_example_question)
        if st.button("Clear index", key="clear_index"):
            _clear_index()
        st.caption(status_line(st.session_state.pipeline, st.session_state.documents))


def _use_example_question() -> None:
    import streamlit as st

    st.session_state.question = st.session_state.example_question
    st.session_state.response = None
    st.session_state.error = None


def _documents() -> None:
    import streamlit as st

    st.subheader("Documents")
    st.caption(
        "Supported types: .pdf, .txt, .md, and .markdown. "
        "Each file can be up to 20 MB. "
        "An uploaded name is only a file name. It is not opened as a path."
    )
    uploaded = st.file_uploader(
        "Upload files",
        type=[suffix.lstrip(".") for suffix in SUPPORTED_EXTENSIONS],
        accept_multiple_files=True,
        key=f"uploads-{st.session_state.upload_generation}",
        help="These files are added to the session index.",
    )
    upload_column, sample_column = st.columns(2)
    with upload_column:
        if st.button("Index uploaded files", key="index_uploads"):
            _index_uploaded(uploaded)
    with sample_column:
        if st.button("Load sample corpus", key="load_sample"):
            _load_sample()
    st.caption(
        "The sample corpus is the refund policy, the cancellation policy, the employee handbook, "
        "and the terms. refund-policy.pdf states the 30-day rule on page 4."
    )
    if st.session_state.note:
        st.caption(st.session_state.note)
    rows = document_rows(st.session_state.documents)
    if rows:
        st.dataframe(rows, hide_index=True, use_container_width=True)
    else:
        st.info("No documents yet. Upload files, or load the sample corpus.")


def _index_uploaded(uploaded) -> None:
    import streamlit as st

    pipeline = st.session_state.pipeline
    try:
        prepared = prepare_uploads(
            _file_payloads(uploaded),
            max_bytes=pipeline.settings.max_upload_bytes,
        )
        batch = ingest_prepared(pipeline, prepared)
    except WebUIError as exc:
        st.session_state.error = str(exc)
        return
    except Exception as exc:
        st.session_state.error = public_error(exc, pipeline.settings.resolved_api_key())
        return
    st.session_state.documents.extend(batch.indexed)
    st.session_state.note = describe_ingest(batch)
    st.session_state.response = None
    st.session_state.error = "\n".join(batch.errors) if batch.errors else None
    if batch.indexed:
        st.session_state.upload_generation += 1
        st.rerun()


def _load_sample() -> None:
    import streamlit as st

    pipeline = new_pipeline()
    try:
        batch = ingest_prepared(pipeline, sample_files())
    except WebUIError as exc:
        st.session_state.error = str(exc)
        return
    except Exception as exc:
        st.session_state.error = public_error(exc)
        return
    st.session_state.pipeline = pipeline
    st.session_state.documents = list(batch.indexed)
    st.session_state.note = describe_ingest(batch)
    st.session_state.response = None
    st.session_state.history = []
    st.session_state.error = "\n".join(batch.errors) if batch.errors else None
    st.rerun()


def _clear_index() -> None:
    import streamlit as st

    st.session_state.pipeline = new_pipeline()
    st.session_state.documents = []
    st.session_state.response = None
    st.session_state.history = []
    st.session_state.error = None
    st.session_state.note = "Cleared the session index."
    st.rerun()


def _ask() -> None:
    import streamlit as st

    pipeline = st.session_state.pipeline
    question = str(st.session_state.question)
    try:
        set_answerer(pipeline, st.session_state.provider)
        response = ask(
            pipeline,
            question,
            top_k=st.session_state.top_k,
            debug=bool(st.session_state.show_retrieved),
            document_count=len(st.session_state.documents),
        )
    except WebUIError as exc:
        st.session_state.response = None
        st.session_state.error = str(exc)
        st.rerun()
        return
    except Exception as exc:
        st.session_state.response = None
        st.session_state.error = public_error(exc, pipeline.settings.resolved_api_key())
        st.rerun()
        return
    st.session_state.response = response
    st.session_state.error = None
    st.session_state.history.append(
        {
            "question": question.strip(),
            "answer": response.answer,
            "citations": [citation_line(citation) for citation in response.citations],
        }
    )
    if len(st.session_state.history) > MAX_HISTORY:
        del st.session_state.history[:-MAX_HISTORY]
    st.rerun()


def _render_feedback() -> None:
    import streamlit as st

    if st.session_state.error:
        st.error(st.session_state.error)


def _render_answer() -> None:
    import streamlit as st

    earlier = st.session_state.history
    if st.session_state.response is not None and earlier:
        earlier = earlier[:-1]
    if earlier:
        with st.expander(f"Earlier answers ({len(earlier)})"):
            for turn in earlier:
                st.text(turn["question"])
                st.text(turn["answer"])
                for line in turn.get("citations") or []:
                    st.caption(line)

    response = st.session_state.response
    if response is None:
        return

    st.subheader("Answer")
    if response.answer == INSUFFICIENT_ANSWER:
        st.info(response.answer)
    else:
        st.text(response.answer)

    pipeline = st.session_state.pipeline
    columns = st.columns(3)
    columns[0].metric("Citations", len(response.citations))
    if response.retrieved is None:
        columns[1].metric("Retrieved", "off")
    else:
        columns[1].metric("Retrieved", len(response.retrieved))
    columns[2].metric("Answerer", pipeline.generator.name)

    citations_tab, retrieved_tab = st.tabs(["Citations", "Retrieved chunks"])
    with citations_tab:
        _render_citations(response)
    with retrieved_tab:
        _render_retrieved(response)

    st.download_button(
        "Download answer",
        data=render_answer_text(response),
        file_name="answer.txt",
        mime="text/plain",
        key="download_answer",
    )
    st.download_button(
        "Download JSON",
        data=render_json(response) + "\n",
        file_name="answer.json",
        mime="application/json",
        key="download_json",
    )


def _render_citations(response: RAGResponse) -> None:
    import streamlit as st

    rows = citation_rows(response)
    if rows:
        st.dataframe(rows, hide_index=True, use_container_width=True)
    else:
        st.info("No citations.")
    retrieved = {chunk.chunk_id: chunk for chunk in response.retrieved or []}
    for citation in response.citations:
        with st.expander(citation_line(citation)):
            chunk = retrieved.get(citation.chunk_id)
            if chunk is None:
                st.caption("Turn on retrieved chunks to read the cited text.")
            else:
                st.text(chunk.text)


def _render_retrieved(response: RAGResponse) -> None:
    import streamlit as st

    if response.retrieved is None:
        st.info("Retrieved chunks are off for this answer.")
        return
    rows = retrieved_rows(response)
    if rows:
        st.dataframe(rows, hide_index=True, use_container_width=True)
    else:
        st.info("No chunks were retrieved.")
    for chunk in response.retrieved:
        with st.expander(retrieved_caption(chunk)):
            st.text(chunk.text)


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
