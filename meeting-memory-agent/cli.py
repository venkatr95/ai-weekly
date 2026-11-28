"""Command-line interface for the meeting-memory agent."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from meeting_memory.config import Settings
from meeting_memory.errors import MeetingMemoryError
from meeting_memory.evaluation import evaluate, load_questions
from meeting_memory.pipeline import MeetingMemory
from meeting_memory.rendering import (
    format_evidence,
    render_answer_json,
    render_answer_markdown,
    render_evaluation,
    render_ingest,
    render_summary_json,
)
from meeting_memory.schemas import MemoryItem


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except MeetingMemoryError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--index-dir", type=Path, default=None, help="Directory for the local index.")

    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="Build a searchable memory of meeting decisions, commitments, and open questions.",
        parents=[common],
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest", parents=[common], help="Index transcripts or recordings.")
    ingest.add_argument("path", type=Path, help="A meeting file or a directory of meetings.")
    ingest.add_argument("--rebuild", action="store_true", help="Replace the existing index.")
    ingest.set_defaults(handler=command_ingest)

    index = subparsers.add_parser("index", parents=[common], help="Index transcripts or recordings.")
    index.add_argument("path", type=Path, help="A meeting file or a directory of meetings.")
    index.add_argument("--rebuild", action="store_true", help="Replace the existing index.")
    index.set_defaults(handler=command_ingest)

    import_parser = subparsers.add_parser("import", parents=[common], help="Import a transcript.")
    import_parser.add_argument("path", type=Path, help="A transcript file or a directory of transcripts.")
    import_parser.add_argument("--rebuild", action="store_true", help="Replace the existing index.")
    import_parser.set_defaults(handler=command_import)

    transcribe = subparsers.add_parser("transcribe", parents=[common], help="Transcribe a recording locally.")
    transcribe.add_argument("path", type=Path, help="An audio recording.")
    transcribe.set_defaults(handler=command_transcribe)

    ask = subparsers.add_parser("ask", parents=[common], help="Ask a question across indexed meetings.")
    ask.add_argument("question", help="Natural-language question.")
    ask.add_argument("--format", choices=("markdown", "json"), default="markdown")
    ask.set_defaults(handler=command_ask)

    meetings = subparsers.add_parser("meetings", parents=[common], help="List indexed meetings.")
    meetings.set_defaults(handler=command_meetings)

    show = subparsers.add_parser("show", parents=[common], help="Print one meeting transcript.")
    show.add_argument("meeting", help="Meeting id or name.")
    show.set_defaults(handler=command_show)

    summary = subparsers.add_parser("summary", parents=[common], help="Summarize one meeting.")
    summary.add_argument("meeting", help="Meeting id or name.")
    summary.add_argument("--format", choices=("markdown", "json"), default="markdown")
    summary.set_defaults(handler=command_summary)

    report = subparsers.add_parser("report", parents=[common], help="Generate a meeting report.")
    report.add_argument("meeting", help="Meeting id, M00N label, or name.")
    report.add_argument("--format", choices=("markdown", "json"), default="markdown")
    report.set_defaults(handler=command_summary)

    commitments = subparsers.add_parser("commitments", parents=[common], help="List commitments.")
    commitments.add_argument("--status", default=None, help="Filter by status, for example open or done.")
    commitments.add_argument("--owner", default=None, help="Filter by the responsible person.")
    commitments.set_defaults(handler=command_commitments)

    questions = subparsers.add_parser("questions", parents=[common], help="List questions.")
    questions.add_argument("--status", default="unresolved", help="Filter by status. Use 'all' for every question.")
    questions.set_defaults(handler=command_questions)

    unresolved = subparsers.add_parser("unresolved", parents=[common], help="List unresolved questions.")
    unresolved.set_defaults(handler=command_unresolved)

    decisions = subparsers.add_parser("decisions", parents=[common], help="List decisions.")
    decisions.set_defaults(handler=command_decisions)

    compare = subparsers.add_parser("compare", parents=[common], help="Show records about one topic across meetings.")
    compare.add_argument("topic", help="Topic to compare, for example 'API delivery'.")
    compare.add_argument("--format", choices=("markdown", "json"), default="markdown")
    compare.set_defaults(handler=command_compare)

    evaluate_parser = subparsers.add_parser(
        "evaluate",
        parents=[common],
        help="Score the bundled questions against a fresh index of the sample meetings.",
    )
    evaluate_parser.add_argument("--meetings", type=Path, default=Path("examples/meetings"))
    evaluate_parser.add_argument("--questions", type=Path, default=Path("examples/questions.json"))
    evaluate_parser.add_argument("--output", type=Path, default=None, help="Write the JSON report to this path.")
    evaluate_parser.set_defaults(handler=command_evaluate)

    delete = subparsers.add_parser("delete", parents=[common], help="Delete one meeting, or the whole index.")
    delete.add_argument("meeting", nargs="?", help="Meeting id, M00N label, or name.")
    delete.add_argument("--all", action="store_true", help="Delete every indexed meeting.")
    delete.add_argument("--yes", action="store_true", help="Confirm deletion of every meeting.")
    delete.set_defaults(handler=command_delete)

    speakers = subparsers.add_parser("speakers", parents=[common], help="Map anonymous speaker labels.")
    speaker_commands = speakers.add_subparsers(dest="speakers_command", required=True)
    speaker_map = speaker_commands.add_parser("map", parents=[common], help="Map one label to a participant.")
    speaker_map.add_argument("meeting", help="Meeting id, M00N label, or name.")
    speaker_map.add_argument("--label", required=True, help="Anonymous label, for example SPEAKER_00.")
    speaker_map.add_argument("--name", required=True, help="Participant name.")
    speaker_map.add_argument("--confidence", type=float, default=1.0)
    speaker_map.set_defaults(handler=command_map_speaker)

    search = subparsers.add_parser("search", parents=[common], help="Search indexed commitments and decisions.")
    search.add_argument("query", help="Words to search for.")
    search.add_argument("--owner", default=None)
    search.add_argument("--kind", default=None)
    search.add_argument("--status", default=None)
    search.set_defaults(handler=command_search)
    return parser


def command_import(args: argparse.Namespace) -> int:
    return command_ingest(args)


def command_transcribe(args: argparse.Namespace) -> int:
    memory = _memory(args)
    memory.settings = memory.settings.model_copy(update={"transcriber": "whisper"})
    report = memory.ingest(args.path)
    print(render_ingest(report))
    if report.meetings_added == 0:
        return 1
    for meeting in memory.meetings():
        if meeting.origin != "whisper":
            continue
        print(f"# {meeting.name}")
        for utterance in meeting.utterances:
            stamp = f"[{utterance.start}] " if utterance.start else ""
            speaker = f"{utterance.speaker}: " if utterance.speaker else ""
            print(f"{stamp}{speaker}{utterance.text}")
    return 0


def command_ingest(args: argparse.Namespace) -> int:
    memory = _memory(args)
    report = memory.ingest(args.path, rebuild=args.rebuild)
    print(render_ingest(report))
    return 0 if report.meetings_added else 1


def command_ask(args: argparse.Namespace) -> int:
    answer = _memory(args).ask(args.question)
    print(render_answer_json(answer) if args.format == "json" else render_answer_markdown(answer))
    return 0


def command_meetings(args: argparse.Namespace) -> int:
    memory = _memory(args)
    meetings = memory.meetings()
    if not meetings:
        print("No meetings are indexed.")
        return 0
    items = memory.items()
    for index, meeting in enumerate(meetings, start=1):
        count = sum(1 for item in items if item.meeting_id == meeting.meeting_id and item.kind != "status")
        held = meeting.held_on or "undated"
        print(
            f"M{index:03d}  {meeting.meeting_id}  {held}  {meeting.name}  "
            f"utterances={len(meeting.utterances)}  items={count}"
        )
    return 0


def command_show(args: argparse.Namespace) -> int:
    meeting = _memory(args).get_meeting(args.meeting)
    print(f"# {meeting.name}")
    print(f"Id: {meeting.meeting_id}")
    print(f"Held: {meeting.held_on or 'date not recorded'}")
    print(f"Language: {meeting.language or 'not recorded'}")
    print(f"Origin: {meeting.origin}")
    print(f"Status: {meeting.processing_status}")
    if meeting.speaker_map:
        pairs = ", ".join(f"{label} -> {name}" for label, name in sorted(meeting.speaker_map.items()))
        print(f"Speaker map: {pairs}")
    print()
    for utterance in meeting.utterances:
        stamp = f"[{utterance.start}] " if utterance.start else ""
        speaker = f"{utterance.speaker}: " if utterance.speaker else ""
        print(f"{stamp}{speaker}{utterance.text}")
    return 0


def command_summary(args: argparse.Namespace) -> int:
    summary = _memory(args).summary(args.meeting)
    print(render_summary_json(summary) if args.format == "json" else summary.markdown)
    return 0


def command_commitments(args: argparse.Namespace) -> int:
    memory = _memory(args)
    items = [item for item in memory.items(status=args.status) if item.kind in {"commitment", "task"}]
    if args.owner:
        items = [item for item in items if item.owner and item.owner.casefold() == args.owner.casefold()]
    _print_items(items)
    return 0


def command_unresolved(args: argparse.Namespace) -> int:
    args.status = "unresolved"
    return command_questions(args)


def command_questions(args: argparse.Namespace) -> int:
    status = None if args.status == "all" else args.status
    _print_items(_memory(args).items(kind="question", status=status))
    return 0


def command_decisions(args: argparse.Namespace) -> int:
    _print_items(_memory(args).items(kind="decision"))
    return 0


def command_compare(args: argparse.Namespace) -> int:
    answer = _memory(args).compare(args.topic)
    print(render_answer_json(answer) if args.format == "json" else render_answer_markdown(answer))
    return 0


def command_delete(args: argparse.Namespace) -> int:
    memory = _memory(args)
    if args.all:
        if not args.yes:
            print("Refusing to delete every meeting without --yes.", file=sys.stderr)
            return 2
        memory.clear()
        print("Deleted every indexed meeting.")
        return 0
    if not args.meeting:
        print("Name a meeting, or pass --all --yes.", file=sys.stderr)
        return 2
    name = memory.delete(args.meeting)
    print(f"Deleted {name}.")
    return 0


def command_map_speaker(args: argparse.Namespace) -> int:
    meeting = _memory(args).map_speakers(args.meeting, args.label, args.name, args.confidence)
    print(f"Mapped {args.label} to {args.name} in {meeting.name}.")
    return 0


def command_search(args: argparse.Namespace) -> int:
    items = _memory(args).search(args.query, kind=args.kind, owner=args.owner, status=args.status)
    _print_items(items)
    return 0


def command_evaluate(args: argparse.Namespace) -> int:
    if args.index_dir is None:
        args.index_dir = Path(tempfile.mkdtemp(prefix="meeting-memory-eval-"))
    memory = _memory(args)
    report = memory.ingest(args.meetings)
    print(render_ingest(report))
    if report.meetings_added == 0:
        return 1
    scores = evaluate(memory, load_questions(args.questions))
    print(render_evaluation(scores))
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(scores.model_dump_json(indent=2), encoding="utf-8")
    return 0 if scores.all_passed else 1


def _memory(args: argparse.Namespace) -> MeetingMemory:
    return MeetingMemory(Settings.from_env(index_dir=args.index_dir))


def _print_items(items: list[MemoryItem]) -> None:
    if not items:
        print("None recorded.")
        return
    for item in items:
        owner = item.owner or "unassigned"
        deadline = item.deadline_iso or item.deadline_wording or "none"
        print(f"{item.item_id}  {item.kind}  {item.status}  {item.evidence_type}  {owner}  {deadline}")
        print(f"  {item.text}")
        print(f"  {format_evidence(item.evidence)}")


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue


if __name__ == "__main__":
    sys.exit(main())
