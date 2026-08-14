"""Summarize what's new across your documents since the last time this ran.

Usage: python daily_digest.py
Intended to be run on a schedule (cron / Task Scheduler) for a "what changed" readout.
"""

import json
import os
from datetime import datetime, timezone

from rag_core import get_llm, list_source_files, load_manifest, sync_vectorstore, get_embeddings, get_vectorstore

DIGEST_STATE_PATH = "./digest_state.json"
MAX_CHARS_PER_FILE = 6000  # keep the digest prompt bounded on large files


def load_last_run() -> str | None:
    if not os.path.exists(DIGEST_STATE_PATH):
        return None
    with open(DIGEST_STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f).get("last_run")


def save_last_run(timestamp: str) -> None:
    with open(DIGEST_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump({"last_run": timestamp}, f, indent=2)


def read_excerpt(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(MAX_CHARS_PER_FILE)
    except UnicodeDecodeError:
        return ""  # binary (e.g. PDF) — the digest just names it, doesn't excerpt it


def main():
    print("Checking for new or changed documents...")
    embeddings = get_embeddings()
    vectorstore = get_vectorstore(embeddings)
    sync_vectorstore(vectorstore)  # picks up anything dropped into docs/ since last run

    last_run = load_last_run()
    manifest = load_manifest()

    if last_run is None:
        print("First run — treating every indexed document as new.")
        changed_paths = list(manifest.keys())
    else:
        changed_paths = [
            path
            for path, meta in manifest.items()
            if meta.get("indexed_at", "") > last_run
        ]

    now = datetime.now(timezone.utc).isoformat()

    if not changed_paths:
        print("Nothing new since the last digest.")
        save_last_run(now)
        return

    print(f"Found {len(changed_paths)} new/changed document(s). Generating digest...")

    excerpts = []
    for path in changed_paths:
        filename = os.path.basename(path)
        if path.lower().endswith((".txt", ".md")):
            excerpts.append(f"### {filename}\n{read_excerpt(path)}")
        else:
            excerpts.append(f"### {filename}\n(binary document — summarize by filename only)")

    prompt = (
        "The following documents were added or changed in my personal knowledge base "
        "since the last digest. Write a short digest (a few sentences per document, "
        "plus a one-paragraph overall summary) of what's new:\n\n"
        + "\n\n".join(excerpts)
    )

    llm = get_llm()
    response = llm.invoke(prompt)

    print("\n" + "=" * 60)
    print("DAILY DIGEST")
    print("=" * 60)
    print(response.content)
    print("=" * 60)

    save_last_run(now)


if __name__ == "__main__":
    main()
