"""Command-line interface for EDM."""

from __future__ import annotations

import argparse
import json
import sys

from edm import __version__
from edm.errors import EdmError
from edm.service import Edm
from edm.win32.dpi import ensure_dpi_awareness


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
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("doctor", help="Inspect EDM environment and desktop session.")
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

    if args.command == "doctor":
        ensure_dpi_awareness()
        try:
            result = Edm.build_default().doctor()
        except EdmError as exc:
            print(json.dumps(exc.to_payload(), ensure_ascii=False), file=sys.stderr)
            return 2
        print(json.dumps(result.payload, ensure_ascii=False))
        return 0

    parser.print_help()
    return 0
