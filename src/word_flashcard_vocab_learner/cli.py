"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from . import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="word-flashcard",
        description="Turn your own reading into a spaced-repetition vocabulary deck.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--deck",
        default="deck.json",
        help="path to the deck file (default: deck.json)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    build_parser().parse_args(argv)
    print("word-flashcard: no command yet. Coming next: scan / review / stats / demo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
