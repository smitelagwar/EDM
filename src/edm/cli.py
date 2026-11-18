"""Command-line interface for EDM."""

from __future__ import annotations

import argparse
import sys

from edm import __version__


def build_parser() -> argparse.ArgumentParser:
    """Create the top-level CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="edm",
        description="Everything Desktop on Me — Windows desktop vision and input control.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show the EDM version and exit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the EDM CLI and return an exit code."""
    if sys.platform != "win32":
        print("EDM yalnızca Windows'ta çalışır", file=sys.stderr)
        return 2

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(f"edm {__version__}")
        return 0

    parser.print_help()
    return 0
