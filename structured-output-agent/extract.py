"""Structured Output Agent — CLI entry point.

Usage:
  # Single message from command line
  python extract.py "My payment failed twice. Please refund me."

  # Interactive mode — keeps asking for messages
  python extract.py --interactive

  # Pipe from stdin
  echo "My order never arrived." | python extract.py
"""

import json
import sys

from agent_core import extract_ticket


def run(message: str) -> None:
    """Extract and print a ticket from a single message."""
    print(f"\nMessage: {message}\n")
    try:
        ticket = extract_ticket(message, verbose=True)
        print("\nResult:")
        print(json.dumps(ticket.model_dump(), indent=2))
    except RuntimeError as exc:
        print(f"\nFailed: {exc}", file=sys.stderr)
        sys.exit(1)


def interactive_mode() -> None:
    """Loop asking for messages until the user quits."""
    print("Structured Output Agent — interactive mode")
    print("Type a customer support message (or 'quit' to exit).\n")

    while True:
        try:
            message = input("Message: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not message:
            continue
        if message.lower() in ("quit", "exit", "q"):
            print("Goodbye.")
            break

        run(message)
        print()


def main() -> None:
    args = sys.argv[1:]

    # Interactive flag
    if "--interactive" in args or "-i" in args:
        interactive_mode()
        return

    # Message passed as CLI argument
    if args:
        message = " ".join(args)
        run(message)
        return

    # Message piped via stdin
    if not sys.stdin.isatty():
        message = sys.stdin.read().strip()
        if message:
            run(message)
            return

    # No input — show usage
    print(__doc__)


if __name__ == "__main__":
    main()
