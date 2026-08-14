"""Shared indexing/retrieval logic used by rag.py, streamlit_app.py, and daily_digest.py."""

import hashlib
import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferWindowMemory
from langchain.text_splitter import RecursiveCharacterTextSplitter

DOCS_DIR = "./docs"
DB_DIR = "./chroma_db"
MANIFEST_PATH = "./index_manifest.json"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Default chat model per LLM_PROVIDER. Override with LLM_MODEL if you want a
# different model on the same provider.
PROVIDER_DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-5",
    "openai": "gpt-5.1",
    "gemini": "gemini-3-pro",
    "grok": "grok-4.1",
}


def get_llm():
    """Instantiate the chat model selected via LLM_PROVIDER (default: anthropic).

    Each provider's API key is read from its own env var by the underlying
    langchain integration (ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY,
    XAI_API_KEY) — see .env.example.
    """
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    if provider not in PROVIDER_DEFAULT_MODELS:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{provider}'. "
            f"Supported: {', '.join(PROVIDER_DEFAULT_MODELS)}"
        )
    model = os.getenv("LLM_MODEL") or PROVIDER_DEFAULT_MODELS[provider]

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model)
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model)
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(model=model)
    if provider == "grok":
        from langchain_xai import ChatXAI

        return ChatXAI(model=model)

SUPPORTED_EXTENSIONS = (".pdf", ".txt", ".md")


def ensure_docs_dir() -> bool:
    """Create docs/ if missing. Returns True if it was just created (empty)."""
    if not os.path.exists(DOCS_DIR):
        os.makedirs(DOCS_DIR)
        return True
    return False


def list_source_files() -> list[str]:
    if not os.path.exists(DOCS_DIR):
        return []
    return [
        os.path.join(DOCS_DIR, f)
        for f in sorted(os.listdir(DOCS_DIR))
        if f.lower().endswith(SUPPORTED_EXTENSIONS)
    ]


def file_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest() -> dict:
    if not os.path.exists(MANIFEST_PATH):
        return {}
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_manifest(manifest: dict) -> None:
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def load_and_split(path: str) -> list:
    if path.lower().endswith(".pdf"):
        loader = PyPDFLoader(path)
    else:
        loader = TextLoader(path, encoding="utf-8")
    documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_documents(documents)
    for chunk in chunks:
        chunk.metadata["source"] = path
        chunk.metadata["filename"] = os.path.basename(path)
    return chunks


def get_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)


def get_vectorstore(embeddings: HuggingFaceEmbeddings) -> Chroma:
    return Chroma(persist_directory=DB_DIR, embedding_function=embeddings)


def sync_vectorstore(vectorstore: Chroma) -> dict:
    """Incrementally index docs/: only (re)embeds new or changed files, and
    drops chunks for files that were changed or removed. Returns a summary dict.
    """
    manifest = load_manifest()
    current_files = list_source_files()
    current_paths = set(current_files)
    manifest_paths = set(manifest.keys())

    added, updated, removed, unchanged = [], [], [], []

    # Files that disappeared from docs/ since the last sync
    for path in manifest_paths - current_paths:
        vectorstore._collection.delete(where={"source": path})
        removed.append(path)

    for path in current_files:
        new_hash = file_hash(path)
        old_hash = manifest.get(path, {}).get("hash")

        if old_hash == new_hash:
            unchanged.append(path)
            continue

        if old_hash is not None:
            # Content changed — drop the stale chunks before re-adding.
            vectorstore._collection.delete(where={"source": path})
            updated.append(path)
        else:
            added.append(path)

        chunks = load_and_split(path)
        if chunks:
            vectorstore.add_documents(chunks)

        manifest[path] = {
            "hash": new_hash,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
        }

    for path in removed:
        manifest.pop(path, None)

    save_manifest(manifest)

    return {
        "added": added,
        "updated": updated,
        "removed": removed,
        "unchanged": len(unchanged),
    }


def build_chain(vectorstore: Chroma, memory: ConversationBufferWindowMemory | None = None):
    llm = get_llm()

    if memory is None:
        memory = ConversationBufferWindowMemory(
            memory_key="chat_history",
            return_messages=True,
            output_key="answer",
            k=10,
        )

    return ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=vectorstore.as_retriever(search_kwargs={"k": 4}),
        memory=memory,
        return_source_documents=True,
        verbose=False,
    )


def format_sources(source_documents: list) -> list[str]:
    """Dedup source documents into human-readable citation strings."""
    seen = set()
    citations = []
    for doc in source_documents:
        filename = doc.metadata.get("filename", "unknown")
        page = doc.metadata.get("page")
        label = f"{filename} (page {page + 1})" if page is not None else filename
        if label not in seen:
            seen.add(label)
            citations.append(label)
    return citations
