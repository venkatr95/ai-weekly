"""Run the pipeline on the sample corpus and print each stage.

The default answerer quotes retrieved sentences, so the demo works with no API key.
Pass --llm auto after setting XAI_API_KEY to answer with grok-4.7 instead.
"""

import argparse
import logging
import os
from pathlib import Path

from app.config import make_settings
from app.logging_config import configure_logging
from app.pipeline import build_pipeline
from app.sample_pdf import build_refund_policy_pdf

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the sample document collection a question")
    parser.add_argument("question", nargs="*", default=["What is the refund period?"])
    parser.add_argument(
        "--llm",
        choices=["auto", "extractive", "xai"],
        default="extractive",
        help="extractive quotes the sources; auto or xai calls grok when XAI_API_KEY is set",
    )
    parser.add_argument(
        "--pdf-only",
        action="store_true",
        help="Index only the generated refund-policy PDF so the citation includes a page number",
    )
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    configure_logging("INFO")
    settings = make_settings(
        vector_store="memory",
        embedding_provider="hashing",
        llm_provider=args.llm,
        xai_api_key=os.environ.get("XAI_API_KEY"),
        xai_base_url=os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1"),
        llm_model=os.environ.get("LLM_MODEL", "grok-4.7"),
        reasoning_effort=os.environ.get("REASONING_EFFORT", "low"),
        chunk_size_tokens=500,
        chunk_overlap_tokens=100,
        top_k=args.top_k,
        log_level="INFO",
    )
    pipeline = build_pipeline(settings)
    if args.pdf_only:
        pipeline.ingest("refund-policy.pdf", build_refund_policy_pdf(), "application/pdf")
    else:
        corpus = ROOT / "evaluation" / "corpus"
        for path in sorted(corpus.glob("*.md")):
            pipeline.ingest(path.name, path.read_bytes(), "text/markdown")
        pipeline.ingest("refund-policy.pdf", build_refund_policy_pdf(), "application/pdf")

    question = " ".join(args.question)
    response = pipeline.answer(question, top_k=args.top_k, debug=True)
    print("\nFINAL ANSWER")
    print(response.answer)
    if not response.citations:
        print("(no citations)")
    for citation in response.citations:
        page = "n/a" if citation.page is None else str(citation.page)
        print(f"[{citation.id}] {citation.document}, page {page}, {citation.chunk_id}")


if __name__ == "__main__":
    logging.getLogger("rag_agent").setLevel(logging.INFO)
    main()
