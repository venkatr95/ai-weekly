"""Personal RAG Assistant — CLI chat over your local documents, with memory."""

from rag_core import (
    build_chain,
    ensure_docs_dir,
    format_sources,
    get_embeddings,
    get_vectorstore,
    list_source_files,
    sync_vectorstore,
)


def main():
    if ensure_docs_dir():
        print("Created docs/ folder. Add your PDFs, .txt, or .md files there and re-run.")
        return

    if not list_source_files():
        print("No documents found in docs/. Add files and try again.")
        return

    print("Indexing documents...")
    embeddings = get_embeddings()
    vectorstore = get_vectorstore(embeddings)
    summary = sync_vectorstore(vectorstore)

    if summary["added"]:
        print(f"  Added: {len(summary['added'])} file(s)")
    if summary["updated"]:
        print(f"  Updated: {len(summary['updated'])} file(s)")
    if summary["removed"]:
        print(f"  Removed: {len(summary['removed'])} file(s)")
    print(f"  Unchanged (skipped): {summary['unchanged']} file(s)")

    chain = build_chain(vectorstore)
    print("\nRAG Assistant ready. Type your questions (type 'quit' to exit):\n")

    while True:
        question = input("You: ")
        if question.lower() in ("quit", "exit", "q"):
            break

        response = chain.invoke({"question": question})
        print(f"\nAssistant: {response['answer']}")

        citations = format_sources(response.get("source_documents", []))
        if citations:
            print(f"Sources: {', '.join(citations)}")
        print()


if __name__ == "__main__":
    main()
