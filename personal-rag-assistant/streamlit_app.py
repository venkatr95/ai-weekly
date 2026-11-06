"""Web UI for the Personal RAG Assistant. Run with: streamlit run streamlit_app.py"""

from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SAMPLE_NOTE = ROOT / "examples" / "sample_note.md"
SUGGESTIONS = {
    ":material/summarize: Summarize": "Summarize the main points in these documents.",
    ":material/lightbulb: What should I remember?": "What facts should I remember from these documents?",
}
# Keep in step with rag_core.SUPPORTED_EXTENSIONS.
SUPPORTED_EXTENSIONS = (".pdf", ".txt", ".md")
MAX_UPLOAD_BYTES = 32 * 1024 * 1024
_UNSAFE_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_SECRET_ENV_VARS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY", "XAI_API_KEY")


class WebUIError(Exception):
    """A problem the page can show without a traceback."""


def display_name(path: str) -> str:
    """File name only. A stored path is not shown in the sidebar."""

    name = Path(str(path).replace("\\", "/")).name
    return name or "unknown"


def index_message(summary: dict) -> str:
    """One line for the dict returned by rag_core.sync_vectorstore."""

    return (
        f"Added {len(summary['added'])}, "
        f"updated {len(summary['updated'])}, "
        f"removed {len(summary['removed'])}, "
        f"unchanged {summary['unchanged']}."
    )


def provider_label() -> str:
    """Provider and model from the environment. The API key is not included."""

    import rag_core

    provider = os.getenv("LLM_PROVIDER", "anthropic").strip().lower() or "anthropic"
    model = os.getenv("LLM_MODEL", "").strip()
    if not model:
        model = rag_core.PROVIDER_DEFAULT_MODELS.get(provider, "")
    if model:
        return f"{provider} ({model})"
    return provider


def public_error(exc: BaseException) -> str:
    """Error text with configured API keys removed."""

    text = str(exc).strip() or exc.__class__.__name__
    for name in _SECRET_ENV_VARS:
        secret = os.getenv(name)
        if secret and len(secret) >= 8:
            text = text.replace(secret, "[redacted]")
    if len(text) > 500:
        text = text[:500] + "..."
    return text


def safe_upload_name(name: str, index: int, used: set[str]) -> str:
    """Basename only. A path in the upload name is not opened."""

    base = Path(str(name).replace("\\", "/")).name
    if not base or base in {".", ".."}:
        raise WebUIError(f"Uploaded file {index} has no file name.")
    suffix = Path(base).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        shown = suffix or base
        raise WebUIError(
            f"Unsupported document type '{shown}'. Supported types: .pdf, .txt, .md."
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


def save_uploads(files: list[tuple[str, bytes]], docs_dir: Path) -> list[str]:
    """Write uploads into docs/ and return the saved file names.

    The same file name replaces the copy already in docs/. Names that differ
    only by case share one slot, because Windows treats them as one file.
    """

    if not files:
        raise WebUIError("Choose at least one PDF, TXT, or MD file.")
    docs_dir.mkdir(parents=True, exist_ok=True)
    planned: list[tuple[str, bytes]] = []
    used: set[str] = set()
    for index, (name, data) in enumerate(files, start=1):
        if not isinstance(data, (bytes, bytearray)):
            raise WebUIError(f"Could not read '{name}'.")
        filename = safe_upload_name(str(name), index, used)
        payload = bytes(data)
        if not payload:
            raise WebUIError(f"'{filename}' is empty.")
        if len(payload) > MAX_UPLOAD_BYTES:
            limit = MAX_UPLOAD_BYTES // (1024 * 1024)
            raise WebUIError(f"'{filename}' is larger than {limit} MB.")
        planned.append((filename, payload))

    saved: list[str] = []
    root = docs_dir.resolve()
    for filename, payload in planned:
        target = (docs_dir / filename).resolve()
        if target.parent != root:
            raise WebUIError(f"Refusing to write '{filename}' outside docs/.")
        target.write_bytes(payload)
        saved.append(filename)
    return saved


def install_sample(docs_dir: Path, sample: Path = SAMPLE_NOTE) -> str:
    """Copy the bundled note into docs/ unless that file name is already there."""

    if not sample.is_file():
        raise WebUIError("The sample note is missing.")
    docs_dir.mkdir(parents=True, exist_ok=True)
    target = docs_dir / sample.name
    if target.exists():
        return f"{sample.name} is already in docs/."
    target.write_bytes(sample.read_bytes())
    return f"Added {sample.name}."


_cached_load = None


def load_vectorstore(docs_dir: str):
    """Open the local vector store once per docs directory.

    The embedding model stays in memory across reruns and browser sessions.
    Conversation memory is not cached here. Each conversation builds its own chain.
    """

    global _cached_load
    import streamlit as st

    if _cached_load is None:

        @st.cache_resource(show_spinner=False)
        def _load(path: str):
            import rag_core

            embeddings = rag_core.get_embeddings()
            return rag_core.get_vectorstore(embeddings)

        _cached_load = _load
    return _cached_load(docs_dir)


def ask(chain, question: str) -> tuple[str, list[str]]:
    """Ask the same chain the CLI uses. The chain keeps the conversation memory."""

    import rag_core

    text = question.strip()
    if not text:
        raise WebUIError("Enter a question about your documents.")
    try:
        response = chain.invoke({"question": text})
    except WebUIError:
        raise
    except Exception as exc:
        raise WebUIError(public_error(exc)) from exc
    if not isinstance(response, dict) or "answer" not in response:
        raise WebUIError("The assistant returned an unexpected response.")
    answer = str(response.get("answer") or "").strip()
    if not answer:
        raise WebUIError("The assistant returned an empty answer.")
    raw_sources = rag_core.format_sources(response.get("source_documents") or [])
    return answer, [] if raw_sources is None else list(raw_sources)


def main() -> None:
    import streamlit as st

    st.set_page_config(
        page_title="Personal RAG Assistant",
        page_icon=":material/menu_book:",
        initial_sidebar_state="expanded",
    )
    _init_state()

    st.title("Personal RAG Assistant")
    st.caption(
        "Ask about the PDF, TXT, and MD files in docs/. "
        "Documents are embedded on this machine. "
        "The chat model receives the question and the retrieved passages. "
        "This conversation stays in memory until you clear it."
    )
    _open_index_once()
    if st.session_state.error:
        st.error(st.session_state.error)

    _sidebar()
    if st.session_state.ready and not _source_files():
        st.info(
            "No documents yet. Upload files in the sidebar, add the sample note, "
            "or copy PDF, TXT, or MD files into docs/ and reindex."
        )
    _render_messages()
    suggestion = _suggestion()
    question = st.chat_input(
        "Ask a question about your documents...",
        key="question",
        submit_mode="disable",
    )
    if question:
        _on_question(question)
    elif suggestion:
        _on_question(suggestion)


def _init_state() -> None:
    import streamlit as st

    defaults = {
        "messages": [],
        "error": None,
        "upload_generation": 0,
        "index_note": "",
        "status_note": "",
        "docs_created": False,
        "ready": False,
        "index_attempted": False,
        "vectorstore": None,
        "chain": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _open_index_once() -> None:
    import streamlit as st

    if st.session_state.index_attempted:
        return
    _open_index()


def _open_index() -> None:
    import streamlit as st
    import rag_core

    st.session_state.index_attempted = True
    try:
        with st.spinner("Indexing documents..."):
            created = rag_core.ensure_docs_dir()
            vectorstore = load_vectorstore(str(rag_core.DOCS_DIR))
            summary = rag_core.sync_vectorstore(vectorstore)
    except Exception as exc:
        st.session_state.ready = False
        st.session_state.vectorstore = None
        st.session_state.chain = None
        st.session_state.error = public_error(exc)
        return
    st.session_state.docs_created = bool(created)
    st.session_state.vectorstore = vectorstore
    st.session_state.index_note = index_message(summary)
    st.session_state.ready = True


def _source_files() -> list[str]:
    import rag_core

    return list(rag_core.list_source_files())


def _docs_dir() -> Path:
    import rag_core

    return Path(rag_core.DOCS_DIR)


def _sync_current() -> None:
    import streamlit as st
    import rag_core

    if st.session_state.vectorstore is None:
        return
    summary = rag_core.sync_vectorstore(st.session_state.vectorstore)
    st.session_state.index_note = index_message(summary)
    st.session_state.ready = True


def _chain():
    """Build the chat chain once per conversation.

    ConversationalRetrievalChain stores the last 10 exchanges on this object.
    Clearing the conversation drops it. Reindexing keeps it, because sync
    updates the same vector store the chain already holds.
    """

    import streamlit as st
    import rag_core

    if st.session_state.chain is None:
        st.session_state.chain = rag_core.build_chain(st.session_state.vectorstore)
    return st.session_state.chain


def _sidebar() -> None:
    import streamlit as st

    with st.sidebar:
        st.header("Documents")
        st.caption(f"Chat model: {provider_label()}. Embeddings stay on this machine.")
        uploaded = st.file_uploader(
            "Add documents",
            type=[suffix.lstrip(".") for suffix in SUPPORTED_EXTENSIONS],
            accept_multiple_files=True,
            key=f"uploads-{st.session_state.upload_generation}",
            help="Saved into docs/ under the file name. The same name replaces the existing file.",
        )
        st.caption(f"Each file can be up to {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
        if st.button(
            "Save and index uploads",
            key="save_uploads",
            type="primary",
            icon=":material/upload_file:",
            width="stretch",
        ):
            _save_uploads(uploaded)
            st.rerun()
        if st.button(
            "Add sample note",
            key="add_sample",
            icon=":material/note_add:",
            width="stretch",
        ):
            _add_sample()
            st.rerun()
        if st.button(
            "Reindex documents",
            key="reindex",
            icon=":material/refresh:",
            width="stretch",
            help="Read docs/ again. Unchanged files are skipped.",
        ):
            _reindex()
            st.rerun()
        if st.button(
            "Clear conversation",
            key="clear",
            icon=":material/delete:",
            width="stretch",
            help="Start a new conversation. Indexed documents stay.",
        ):
            _clear_conversation()
            st.rerun()
        _render_library()


def _render_library() -> None:
    import streamlit as st

    files = _source_files() if st.session_state.ready else []
    if files:
        for path in files:
            st.text(display_name(path))
    else:
        st.text("No documents yet.")
    if st.session_state.index_note:
        st.caption(st.session_state.index_note)
    if st.session_state.status_note:
        st.caption(st.session_state.status_note)
    if st.session_state.docs_created and not files:
        st.warning("Created docs/. Add PDF, TXT, or MD files, then reindex.")


def _save_uploads(uploaded) -> None:
    import streamlit as st

    if not uploaded:
        files: list[tuple[str, bytes]] = []
    elif isinstance(uploaded, list):
        files = [(item.name, item.getvalue()) for item in uploaded]
    else:
        files = [(uploaded.name, uploaded.getvalue())]
    try:
        names = save_uploads(files, _docs_dir())
    except WebUIError as exc:
        st.session_state.error = str(exc)
        return
    try:
        _sync_current()
    except Exception as exc:
        st.session_state.status_note = f"Saved {', '.join(names)}."
        st.session_state.error = public_error(exc)
        return
    st.session_state.error = None
    st.session_state.status_note = f"Saved {', '.join(names)}."
    st.session_state.upload_generation += 1


def _add_sample() -> None:
    import streamlit as st

    try:
        note = install_sample(_docs_dir())
    except WebUIError as exc:
        st.session_state.error = str(exc)
        return
    try:
        _sync_current()
    except Exception as exc:
        st.session_state.status_note = note
        st.session_state.error = public_error(exc)
        return
    st.session_state.error = None
    st.session_state.status_note = note


def _reindex() -> None:
    import streamlit as st

    if st.session_state.vectorstore is None:
        st.session_state.index_attempted = False
        _open_index()
        return
    try:
        _sync_current()
    except Exception as exc:
        st.session_state.error = public_error(exc)
        return
    st.session_state.error = None


def _clear_conversation() -> None:
    import streamlit as st

    st.session_state.messages = []
    st.session_state.chain = None
    st.session_state.error = None


def _render_messages() -> None:
    import streamlit as st

    for message in st.session_state.messages:
        _render_message(message)


def _render_message(message: dict) -> None:
    import streamlit as st

    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        sources = message.get("sources") or []
        if sources:
            label = "Source" if len(sources) == 1 else f"Sources ({len(sources)})"
            with st.expander(label):
                for source in sources:
                    st.text(source)


def _on_question(question: str) -> None:
    """Store the exchange, then rerun so the history draws it once."""

    import streamlit as st

    text = question.strip()
    if not text:
        st.session_state.error = "Enter a question about your documents."
        st.rerun()
        return
    if not st.session_state.ready or st.session_state.vectorstore is None:
        st.session_state.error = "Documents are not indexed yet."
        st.rerun()
        return
    if not _source_files():
        st.session_state.error = "Add at least one PDF, TXT, or MD document before asking."
        st.rerun()
        return
    try:
        answer, sources = ask(_chain(), text)
    except WebUIError as exc:
        _record_exchange(text, str(exc), [])
        st.session_state.error = str(exc)
        st.rerun()
        return
    except Exception as exc:
        message = public_error(exc)
        _record_exchange(text, message, [])
        st.session_state.error = message
        st.rerun()
        return
    st.session_state.error = None
    _record_exchange(text, answer, sources)
    st.rerun()


def _record_exchange(question: str, answer: str, sources: list[str]) -> None:
    import streamlit as st

    st.session_state.messages.append({"role": "user", "content": question})
    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "sources": sources}
    )


def _suggestion() -> str | None:
    """Starter questions while the conversation is empty and documents are indexed."""

    import streamlit as st

    if not st.session_state.ready or st.session_state.messages or not _source_files():
        return None
    selected = st.pills(
        "Try asking",
        list(SUGGESTIONS),
        key="suggestion",
        label_visibility="collapsed",
    )
    if not selected:
        return None
    return SUGGESTIONS[selected]


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
