"""Command-line interface for the Personal Document Change Detector."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from document_detector.config import IMPORTANCE_RANK, load_settings
from document_detector.errors import DetectorError
from document_detector.pipeline import compare
from document_detector.report_generator import render_json, render_markdown


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    try:
        return args.handler(args)
    except DetectorError as exc:
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
        description="Compare two document versions and explain meaningful changes.",
        parents=[common],
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    compare_parser = subparsers.add_parser("compare", parents=[common], help="Compare two documents.")
    compare_parser.add_argument("--old", required=True, type=Path, help="Previous document version.")
    compare_parser.add_argument("--new", required=True, type=Path, help="Updated document version.")
    compare_parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    compare_parser.add_argument("--output", type=Path, help="Write the report to this path.")
    compare_parser.add_argument(
        "--min-importance",
        choices=tuple(IMPORTANCE_RANK.keys()),
        default="informational",
        help="Hide changes below this importance level.",
    )
    compare_parser.add_argument(
        "--include-formatting",
        action="store_true",
        help="Keep formatting-only differences in the report.",
    )
    compare_parser.add_argument("--comparison-id", default="comparison_001")
    compare_parser.set_defaults(handler=command_compare)
    return parser


def command_compare(args: argparse.Namespace) -> int:
    settings = load_settings(args.provider)
    report = compare(
        args.old,
        args.new,
        settings=settings,
        min_importance=args.min_importance,
        include_formatting=args.include_formatting,
        comparison_id=args.comparison_id,
    )
    rendered = render_json(report) if args.format == "json" else render_markdown(report)
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(rendered)
    return 0


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def _configure_logging(verbose: int) -> None:
    level = logging.WARNING
    if verbose == 1:
        level = logging.INFO
    elif verbose >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")


if __name__ == "__main__":
    raise SystemExit(main())
