"""Command-line interface for the AI Answer Auditor."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from answer_auditor.config import load_settings
from answer_auditor.document_loader import load_request, read_answer
from answer_auditor.errors import AuditorError
from answer_auditor.evaluation import evaluate_benchmark
from answer_auditor.pipeline import audit, extract_claims
from answer_auditor.report_generator import render_json, render_markdown


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    try:
        return args.handler(args)
    except AuditorError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--verbose", "-v", action="count", default=0, help="Repeat for more log detail.")
    common.add_argument(
        "--provider",
        choices=("heuristic", "xai"),
        default=None,
        help="heuristic is offline. xai calls the model named by XAI_MODEL.",
    )

    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="Check an AI-generated answer against the source documents that were supposed to support it.",
        parents=[common],
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit_parser = subparsers.add_parser("audit", parents=[common], help="Verify an answer against sources.")
    audit_parser.add_argument("--answer", type=Path, help="Text file containing the AI-generated answer.")
    audit_parser.add_argument(
        "--sources",
        nargs="+",
        type=Path,
        help="Source files or directories (.txt, .md, .pdf, .json).",
    )
    audit_parser.add_argument("--question", default=None, help="Original question, used as context.")
    audit_parser.add_argument("--input", type=Path, help="JSON request with an answer and sources.")
    audit_parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    audit_parser.add_argument("--output", type=Path, help="Write the report to this path.")
    audit_parser.set_defaults(handler=command_audit)

    extract_parser = subparsers.add_parser(
        "extract-claims",
        parents=[common],
        help="Split an answer into claims without verifying them.",
    )
    extract_parser.add_argument("--answer", required=True, type=Path)
    extract_parser.set_defaults(handler=command_extract)

    evaluate_parser = subparsers.add_parser(
        "evaluate",
        parents=[common],
        help="Score the auditor against the labeled benchmark.",
    )
    evaluate_parser.add_argument("--benchmark", type=Path, default=Path("examples/benchmark.json"))
    evaluate_parser.set_defaults(handler=command_evaluate)
    return parser


def command_audit(args: argparse.Namespace) -> int:
    settings = load_settings(args.provider)
    if args.input and args.answer:
        raise AuditorError("Pass either --input or --answer, not both.")
    if args.input:
        request = load_request(args.input)
        question = args.question if args.question is not None else request.question
        sources = list(request.sources)
        if args.sources:
            sources.extend(args.sources)
        report = audit(request.answer, sources, question=question, settings=settings)
    else:
        if args.answer is None or not args.sources:
            raise AuditorError("audit requires --answer and --sources, or --input.")
        report = audit(read_answer(args.answer), list(args.sources), question=args.question, settings=settings)
    rendered = render_json(report) if args.format == "json" else render_markdown(report)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


def command_extract(args: argparse.Namespace) -> int:
    settings = load_settings(args.provider)
    claims = extract_claims(read_answer(args.answer), settings=settings)
    print(json.dumps([claim.model_dump(mode="json") for claim in claims], ensure_ascii=False, indent=2))
    return 0


def command_evaluate(args: argparse.Namespace) -> int:
    settings = load_settings("heuristic" if args.provider is None else args.provider)
    if not args.benchmark.is_file():
        raise AuditorError(f"Benchmark file not found: {args.benchmark}")
    report = evaluate_benchmark(args.benchmark, settings=settings)
    print(f"Cases: {report.cases}")
    print(f"Passed: {report.passed}")
    print(f"Verification accuracy: {report.verification_accuracy:.1f}%")
    print(f"Citation validity: {report.citation_validity:.1f}%")
    for result in report.results:
        mark = "pass" if result.passed else "fail"
        print(f"[{mark}] {result.id}: {', '.join(result.actual_statuses) or '(no claims)'}")
        for note in result.notes:
            print(f"  - {note}")
    return 0 if report.passed == report.cases else 1


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue


def _configure_logging(verbosity: int) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")


if __name__ == "__main__":
    sys.exit(main())
