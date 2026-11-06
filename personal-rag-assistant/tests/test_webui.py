"""The web UI uses the same indexing and chat chain as the CLI.

Page tests install a stand-in for rag_core so they do not download embeddings
or call a chat API.
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import pytest

from streamlit_app import (
    SAMPLE_NOTE,
    SUGGESTIONS,
    WebUIError,
    ask,
    display_name,
    index_message,
    install_sample,
    public_error,
    safe_upload_name,
    save_uploads,
)

ROOT = Path(__file__).resolve().parents[1]
SECRET = "sk-personal-rag-test-key"


class FakeChain:
    def __init__(self, core: FakeCore):
        self.core = core
        self.questions: list[str] = []

    def invoke(self, payload: dict) -> dict:
        if self.core.fail_next:
            self.core.fail_next = False
            raise RuntimeError(f"invalid key {SECRET}")
        question = payload["question"]
        self.questions.append(question)
        return {
            "answer": f"From your notes: {question}",
            "source_documents": [{"metadata": {"filename": "sample_note.md"}}],
        }


class FakeCore:
    def __init__(self, docs: Path):
        self.DOCS_DIR = str(docs)
        self.PROVIDER_DEFAULT_MODELS = {
            "anthropic": "claude-sonnet-5",
            "openai": "gpt-5.1",
            "gemini": "gemini-3-pro",
            "grok": "grok-4.1",
        }
        self.syncs = 0
        self.chains: list[FakeChain] = []
        self.known: set[str] = set()
        self.fail_index = False
        self.fail_next = False

    def ensure_docs_dir(self) -> bool:
        path = Path(self.DOCS_DIR)
        existed = path.exists()
        path.mkdir(parents=True, exist_ok=True)
        return not existed

    def list_source_files(self) -> list[str]:
        root = Path(self.DOCS_DIR)
        if not root.exists():
            return []
        return [
            str(root / name)
            for name in sorted(os.listdir(root))
            if name.lower().endswith((".pdf", ".txt", ".md"))
        ]

    def get_embeddings(self):
        if self.fail_index:
            raise RuntimeError("model download failed")
        return object()

    def get_vectorstore(self, embeddings):
        return {"embeddings": embeddings}

    def sync_vectorstore(self, vectorstore) -> dict:
        self.syncs += 1
        current = set(self.list_source_files())
        added = sorted(current - self.known)
        removed = sorted(self.known - current)
        unchanged = len(current & self.known)
        self.known = current
        return {"added": added, "updated": [], "removed": removed, "unchanged": unchanged}

    def build_chain(self, vectorstore) -> FakeChain:
        chain = FakeChain(self)
        self.chains.append(chain)
        return chain

    def format_sources(self, docs) -> list[str]:
        labels = []
        for doc in docs:
            if isinstance(doc, dict):
                labels.append(doc.get("metadata", {}).get("filename", "unknown"))
            else:
                labels.append("unknown")
        return labels


def install_fake(monkeypatch: pytest.MonkeyPatch, docs: Path) -> FakeCore:
    core = FakeCore(docs)
    module = types.ModuleType("rag_core")
    for name in (
        "DOCS_DIR",
        "PROVIDER_DEFAULT_MODELS",
        "ensure_docs_dir",
        "list_source_files",
        "get_embeddings",
        "get_vectorstore",
        "sync_vectorstore",
        "build_chain",
        "format_sources",
    ):
        setattr(module, name, getattr(core, name))
    monkeypatch.setitem(sys.modules, "rag_core", module)
    return core


def page_text(app) -> str:
    parts: list[str] = []
    for group in (app.markdown, app.text, app.error, app.warning, app.caption, app.info, app.success):
        for item in group:
            parts.append(str(item.value))
    return "\n".join(parts)


def test_index_message_and_display_name():
    text = index_message({"added": ["a"], "updated": ["b", "c"], "removed": [], "unchanged": 4})
    assert text == "Added 1, updated 2, removed 0, unchanged 4."
    assert display_name(r"docs\notes\harbor.md") == "harbor.md"
    assert display_name("docs/sample_note.md") == "sample_note.md"


def test_safe_upload_name_keeps_a_basename():
    used: set[str] = set()
    assert safe_upload_name(r"..\..\notes.md", 1, used) == "notes.md"
    assert safe_upload_name("folder/notes.md", 2, used) == "notes-2.md"
    assert safe_upload_name("Notes.MD", 3, used) == "Notes-3.md"
    with pytest.raises(WebUIError, match="Unsupported"):
        safe_upload_name("secret.exe", 4, used)
    with pytest.raises(WebUIError, match="no file name"):
        safe_upload_name("..", 5, used)


def test_save_uploads_writes_inside_docs_only(tmp_path: Path):
    docs = tmp_path / "docs"
    saved = save_uploads(
        [
            (r"..\..\outside.md", b"# Inside\n"),
            ("empty-looking.txt", b"hello"),
        ],
        docs,
    )
    assert saved == ["outside.md", "empty-looking.txt"]
    assert (docs / "outside.md").read_text(encoding="utf-8") == "# Inside\n"
    assert not (tmp_path / "outside.md").exists()

    replaced = save_uploads([("outside.md", b"# Replaced\n")], docs)
    assert replaced == ["outside.md"]
    assert (docs / "outside.md").read_text(encoding="utf-8") == "# Replaced\n"

    with pytest.raises(WebUIError, match="at least one"):
        save_uploads([], docs)
    with pytest.raises(WebUIError, match="empty"):
        save_uploads([("blank.txt", b"")], docs)


def test_save_uploads_rejects_a_file_over_the_limit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    import streamlit_app

    monkeypatch.setattr(streamlit_app, "MAX_UPLOAD_BYTES", 8)
    with pytest.raises(WebUIError, match="larger than"):
        save_uploads([("big.txt", b"012345678")], tmp_path)


def test_sample_note_copies_once(tmp_path: Path):
    docs = tmp_path / "docs"
    first = install_sample(docs)
    assert first == "Added sample_note.md."
    assert (docs / "sample_note.md").read_bytes() == SAMPLE_NOTE.read_bytes()
    assert "30 days" in (docs / "sample_note.md").read_text(encoding="utf-8")
    (docs / "sample_note.md").write_text("edited\n", encoding="utf-8")
    second = install_sample(docs)
    assert second == "sample_note.md is already in docs/."
    assert (docs / "sample_note.md").read_text(encoding="utf-8") == "edited\n"


def test_ask_uses_the_chain_and_redacts_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("XAI_API_KEY", SECRET)
    core = install_fake(monkeypatch, tmp_path)
    chain = core.build_chain(None)
    answer, sources = ask(chain, "  What is the refund period?  ")
    assert answer == "From your notes: What is the refund period?"
    assert sources == ["sample_note.md"]
    assert chain.questions == ["What is the refund period?"]

    with pytest.raises(WebUIError, match="Enter a question"):
        ask(chain, "   ")
    core.fail_next = True
    with pytest.raises(WebUIError, match="redacted") as caught:
        ask(chain, "hello")
    assert SECRET not in str(caught.value)
    assert public_error(RuntimeError(f"bad key {SECRET}")) == "bad key [redacted]"


def _clear_resource_cache() -> None:
    import streamlit as st

    st.cache_resource.clear()


def test_page_indexes_the_sample_and_keeps_conversation_memory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    _clear_resource_cache()
    monkeypatch.setenv("LLM_PROVIDER", "grok")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    core = install_fake(monkeypatch, tmp_path / "docs")
    app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30)
    app.run()
    assert not app.exception
    assert core.syncs == 1
    assert app.session_state.ready is True
    assert app.session_state.messages == []
    assert "grok (grok-4.1)" in page_text(app)
    assert "No documents yet" in page_text(app)

    app.button(key="save_uploads").click().run()
    assert not app.exception
    assert any("at least one" in item.value for item in app.error)
    assert core.syncs == 1

    app.button(key="add_sample").click().run()
    assert not app.exception
    assert (tmp_path / "docs" / "sample_note.md").is_file()
    assert core.syncs == 2
    assert app.session_state.index_note == "Added 1, updated 0, removed 0, unchanged 0."
    assert "sample_note.md" in page_text(app)
    assert app.session_state.error is None
    assert len(app.pills) == 1

    app.chat_input(key="question").set_value("What is the refund period?").run()
    assert not app.exception
    assert len(core.chains) == 1
    assert core.chains[0].questions == ["What is the refund period?"]
    assert app.session_state.messages[0]["content"] == "What is the refund period?"
    assert app.session_state.messages[1]["sources"] == ["sample_note.md"]
    assert "From your notes: What is the refund period?" in page_text(app)
    assert "sample_note.md" in page_text(app)
    assert core.syncs == 2

    app.chat_input(key="question").set_value("When is stand-up?").run()
    assert core.chains[0].questions == ["What is the refund period?", "When is stand-up?"]
    assert len(core.chains) == 1

    app.button(key="reindex").click().run()
    assert not app.exception
    assert core.syncs == 3
    assert app.session_state.index_note == "Added 0, updated 0, removed 0, unchanged 1."
    assert len(core.chains) == 1

    app.button(key="clear").click().run()
    assert app.session_state.messages == []
    assert app.session_state.chain is None
    app.chat_input(key="question").set_value("When does Harbor launch?").run()
    assert len(core.chains) == 2
    assert core.chains[1].questions == ["When does Harbor launch?"]
    assert not app.pills

    app.button(key="clear").click().run()
    label = next(iter(SUGGESTIONS))
    app.pills[0].set_value(label).run()
    assert not app.exception
    assert app.session_state.messages[0]["content"] == SUGGESTIONS[label]
    assert core.chains[-1].questions == [SUGGESTIONS[label]]


def test_page_blocks_an_empty_library_and_redacts_model_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    _clear_resource_cache()
    monkeypatch.setenv("XAI_API_KEY", SECRET)
    monkeypatch.setenv("LLM_PROVIDER", "grok")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    core = install_fake(monkeypatch, tmp_path / "docs")
    core.fail_index = True
    app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30)
    app.run()
    assert not app.exception
    assert app.session_state.ready is False
    assert any("model download failed" in item.value for item in app.error)

    core.fail_index = False
    app.button(key="reindex").click().run()
    assert not app.exception
    assert app.session_state.ready is True
    assert core.syncs == 1

    app.chat_input(key="question").set_value("What is the refund period?").run()
    assert not app.exception
    assert core.chains == []
    assert app.session_state.messages == []
    assert any("at least one" in item.value for item in app.error)

    app.chat_input(key="question").set_value("   ").run()
    assert any("Enter a question" in item.value for item in app.error)

    app.button(key="add_sample").click().run()
    core.fail_next = True
    app.chat_input(key="question").set_value("What is the refund period?").run()
    assert not app.exception
    assert SECRET not in page_text(app)
    assert "[redacted]" in page_text(app)
    assert app.session_state.messages[1]["content"].startswith("invalid key")
    assert SECRET not in app.session_state.messages[1]["content"]
