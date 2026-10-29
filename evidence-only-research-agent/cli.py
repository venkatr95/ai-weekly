"""Command-line interface for the evidence-only research agent."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import tempfile
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from evidence_agent.config import Settings
from evidence_agent.errors import ConfigurationError, EvidenceAgentError
from evidence_agent.evaluation import evaluate, format_report, load_questions
from evidence_agent.pipeline import ResearchPipeline
from evidence_agent.rendering import render_markdown, render_passages


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    try:
        return args.handler(args)
    except EvidenceAgentError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--index-dir", type=Path, default=None, help="Directory for the local index.")
    common.add_argument("--verbose", "-v", action="count", default=0, help="Repeat for more log detail.")

    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="Answer questions from a folder of documents, with citations or an explicit abstention.",
        parents=[common],
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    index = subparsers.add_parser("index", parents=[common], help="Index PDF, Markdown, and text files.")
    index.add_argument("path", type=Path, help="Document file or directory.")
    index.add_argument("--rebuild", action="store_true", help="Replace the existing index.")
    index.add_argument("--chunk-size", type=int, default=None)
    index.add_argument("--chunk-overlap", type=int, default=None)
    index.set_defaults(handler=command_index)

    ask = subparsers.add_parser("ask", parents=[common], help="Ask a question against the index.")
    ask.add_argument("question", help="Research question.")
    ask.add_argument("--format", choices=("markdown", "json"), default="markdown")
    ask.add_argument("--show-passages", action="store_true", help="Show retrieved passages. Scores are not evidence.")
    ask.add_argument("--k", type=int, default=None, help="Number of passages to retrieve.")
    ask.add_argument("--threshold", type=float, default=None, help="Minimum hybrid retrieval score.")
    ask.set_defaults(handler=command_ask)

    sources = subparsers.add_parser("sources", parents=[common], help="List indexed documents.")
    sources.set_defaults(handler=command_sources)

    show = subparsers.add_parser("show-source", parents=[common], help="Print one indexed chunk.")
    show.add_argument("source_id", help="Chunk id.")
    show.set_defaults(handler=command_show_source)

    stats = subparsers.add_parser("stats", parents=[common], help="Show index statistics.")
    stats.set_defaults(handler=command_stats)

    evaluate_parser = subparsers.add_parser("evaluate", parents=[common], help="Score the bundled gold questions.")
    evaluate_parser.add_argument("--documents", type=Path, default=Path("examples/documents"))
    evaluate_parser.add_argument("--questions", type=Path, default=Path("examples/questions.json"))
    evaluate_parser.add_argument("--output", type=Path, default=None, help="Write the JSON report to this path.")
    evaluate_parser.add_argument("--k", type=int, default=None)
    evaluate_parser.add_argument(
        "--provider",
        choices=("extractive", "configured"),
        default="extractive",
        help="extractive is offline. configured uses GENERATION_PROVIDER from the environment.",
    )
    evaluate_parser.set_defaults(handler=command_evaluate)
    return parser


def command_index(args: argparse.Namespace) -> int:
    settings = _settings(args)
    if args.chunk_size is not None:
        settings.chunk_size = args.chunk_size
    if args.chunk_overlap is not None:
        settings.chunk_overlap = args.chunk_overlap
    _revalidate(settings)
    report = ResearchPipeline(settings).index_path(args.path, rebuild=args.rebuild)
    stats = report.stats
    print(f"Indexed {stats.files_indexed} documents ({stats.chunks} chunks).")
    print(f"Reused without re-extraction: {stats.files_reused}")
    print(f"Skipped unsupported files: {stats.files_skipped}")
    print(f"Empty files: {stats.files_empty}")
    print(f"OCR required: {stats.files_needs_ocr}")
    print(f"Failed: {stats.files_failed}")
    print(f"Embedding: {report.embedding_provider} ({report.embedding_dimensions} dimensions)")
    print(f"Index: {report.index_dir}")
    for warning in report.ocr_warnings:
        print(f"OCR: {warning}")
    for error in report.errors:
        print(f"Failed file: {error}", file=sys.stderr)
    if stats.files_indexed == 0:
        return 1
    return 0


def command_ask(args: argparse.Namespace) -> int:
    settings = _settings(args)
    if args.k is not None and args.k < 1:
        raise ConfigurationError("--k must be at least 1.")
    if args.threshold is not None and not 0 <= args.threshold <= 1:
        raise ConfigurationError("--threshold must be between 0 and 1.")
    response, passages = ResearchPipeline(settings).ask(args.question, k=args.k, threshold=args.threshold)
    if args.show_passages:
        rendered = render_passages(passages)
        stream = sys.stderr if args.format == "json" else sys.stdout
        print(rendered, file=stream)
    if args.format == "json":
        print(json.dumps(response.model_dump(), ensure_ascii=False, indent=2))
    else:
        print(render_markdown(response))
    return 0


def command_sources(args: argparse.Namespace) -> int:
    store = ResearchPipeline(_settings(args)).open_index()
    if not store.documents:
        print("The index has no documents.")
        return 0
    print(f"{'path':<48} {'type':<10} {'pages':<6} {'chunks':<7} {'ocr':<4} status")
    for document in store.documents:
        pages = "-" if document.page_count is None else str(document.page_count)
        status = document.error or document.warning or "ok"
        print(
            f"{document.relative_path:<48} {document.file_type:<10} {pages:<6} "
            f"{len(document.chunk_ids):<7} {('yes' if document.needs_ocr else 'no'):<4} {status}"
        )
    return 0


def command_show_source(args: argparse.Namespace) -> int:
    store = ResearchPipeline(_settings(args)).open_index()
    chunk = store.chunks_by_id().get(args.source_id)
    if chunk is None:
        raise ConfigurationError(
            f"No chunk with id {args.source_id!r} is in the index. Run: python cli.py sources"
        )
    print(f"chunk_id: {chunk.chunk_id}")
    print(f"document_id: {chunk.document_id}")
    print(f"source: {chunk.relative_path}")
    print(f"pages: {chunk.page_start}-{chunk.page_end}")
    print("")
    print(chunk.text)
    return 0


def command_stats(args: argparse.Namespace) -> int:
    store = ResearchPipeline(_settings(args)).open_index()
    manifest = store.manifest
    stats = manifest.get("stats") or {}
    print(f"Index: {store.index_dir}")
    print(f"Embedding: {manifest.get('embedding_provider')} ({manifest.get('embedding_dimensions')} dimensions)")
    print(f"Chunk size: {manifest.get('chunk_size')} overlap: {manifest.get('chunk_overlap')}")
    for key in (
        "documents",
        "chunks",
        "files_seen",
        "files_indexed",
        "files_reused",
        "files_skipped",
        "files_failed",
        "files_empty",
        "files_needs_ocr",
    ):
        if key in stats:
            print(f"{key}: {stats[key]}")
    errors = manifest.get("errors") or []
    warnings = manifest.get("ocr_warnings") or []
    if warnings:
        print("OCR warnings:")
        for warning in warnings:
            print(f"- {warning}")
    if errors:
        print("Extraction errors:")
        for error in errors:
            print(f"- {error}")
    return 0


def command_evaluate(args: argparse.Namespace) -> int:
    if not args.questions.is_file():
        raise ConfigurationError(f"Question file not found: {args.questions}")
    if not args.documents.exists():
        raise ConfigurationError(f"Document folder not found: {args.documents}")
    questions = load_questions(args.questions)
    settings = _settings(args)
    if args.provider == "extractive":
        settings.generation_provider = "extractive"
        settings.embedding_provider = "local"
    if args.k is not None:
        settings.retrieval_k = args.k
    _revalidate(settings)

    def run(index_dir: Path) -> int:
        settings.index_dir = index_dir
        pipeline = ResearchPipeline(settings)
        report = evaluate(pipeline, args.documents, questions, k=args.k)
        print(format_report(report), end="")
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(report.model_dump(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"Wrote {args.output}")
        return 0

    if args.index_dir is None:
        with tempfile.TemporaryDirectory(prefix="evidence-eval-") as directory:
            return run(Path(directory))
    print("Evaluate rebuilds the index in the selected directory.", file=sys.stderr)
    return run(args.index_dir)


def _settings(args: argparse.Namespace) -> Settings:
    settings = Settings.load()
    if args.index_dir is not None:
        settings.index_dir = args.index_dir
    return settings


def _revalidate(settings: Settings) -> None:
    try:
        Settings.model_validate(settings.model_dump())
    except ValueError as exc:
        raise ConfigurationError(str(exc)) from exc


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue


def _configure_logging(verbose: int) -> None:
    level = logging.WARNING
    if verbose == 1:
        level = logging.INFO
    elif verbose >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s", stream=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
