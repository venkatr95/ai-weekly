"""Command-line interface for the Email-to-Action Agent."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from email_to_action.errors import EmailActionError
from email_to_action.pipeline import analyze
from email_to_action.report import render_json, render_markdown


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    try:
        return args.handler(args)
    except EmailActionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="Turn an email or thread into a validated action list and a draft reply.",
    )
    parser.add_argument("--verbose", "-v", action="count", default=0, help="Repeat for more log detail.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze_parser = subparsers.add_parser("analyze", help="Extract actions from an email file or stdin.")
    analyze_parser.add_argument("--input", type=Path, help="Plain-text email or .eml file. Reads stdin when omitted.")
    analyze_parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    analyze_parser.add_argument("--output", type=Path, help="Write the report to this path as well as stdout.")
    analyze_parser.add_argument("--verbose", "-v", action="count", default=0)
    analyze_parser.set_defaults(handler=command_analyze)
    return parser


def command_analyze(args: argparse.Namespace) -> int:
    if args.input:
        action = analyze(args.input)
    else:
        text = sys.stdin.read()
        if not text.strip():
            raise EmailActionError("No email text on stdin.")
        action = analyze(text)
    rendered = render_json(action) if args.format == "json" else render_markdown(action)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


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
    logging.basicConfig(level=level, format="%(levelname)s %(message)s")


if __name__ == "__main__":
    raise SystemExit(main())
