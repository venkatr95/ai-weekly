"""Web UI for the Personal RAG Assistant. Run with: streamlit run streamlit_app.py"""

import streamlit as st

from rag_core import (
    build_chain,
    ensure_docs_dir,
    format_sources,
    get_embeddings,
    get_vectorstore,
    list_source_files,
    sync_vectorstore,
)

st.set_page_config(page_title="Personal RAG Assistant", page_icon="📚")
st.title("📚 Personal RAG Assistant")


@st.cache_resource
def load_vectorstore():
    embeddings = get_embeddings()
    return get_vectorstore(embeddings)


def reindex():
    with st.spinner("Indexing documents..."):
        summary = sync_vectorstore(st.session_state.vectorstore)
    st.session_state.chain = build_chain(st.session_state.vectorstore)
    return summary


if ensure_docs_dir():
    st.warning("Created docs/ folder. Add PDFs, .txt, or .md files there, then click Reindex.")

if "vectorstore" not in st.session_state:
    st.session_state.vectorstore = load_vectorstore()

if "chain" not in st.session_state:
    st.session_state.chain = build_chain(st.session_state.vectorstore)

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.subheader("Documents")
    files = list_source_files()
    if files:
        for f in files:
            st.text(f"• {f.split('/')[-1]}")
    else:
        st.text("No documents indexed yet.")

    if st.button("🔄 Reindex documents"):
        summary = reindex()
        st.success(
            f"Added {len(summary['added'])}, updated {len(summary['updated'])}, "
            f"removed {len(summary['removed'])}, unchanged {summary['unchanged']}."
        )

    if st.button("🗑️ Clear conversation"):
        st.session_state.messages = []
        st.session_state.chain = build_chain(st.session_state.vectorstore)
        st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sources"):
            with st.expander("Sources"):
                for s in message["sources"]:
                    st.text(s)

if question := st.chat_input("Ask a question about your documents..."):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = st.session_state.chain.invoke({"question": question})
        st.markdown(response["answer"])
        sources = format_sources(response.get("source_documents", []))
        if sources:
            with st.expander("Sources"):
                for s in sources:
                    st.text(s)

    st.session_state.messages.append(
        {"role": "assistant", "content": response["answer"], "sources": sources}
    )
