"""Command-line interface for EDM."""

from __future__ import annotations

import argparse
import json
import sys

from edm import __version__
from edm.errors import EdmError
from edm.service import Edm, Result
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
    subparsers.add_parser("monitors", help="List display monitors.")

    win_p = subparsers.add_parser("windows", help="List top-level windows.")
    win_p.add_argument("--query", default=None, help="Window query selector.")
    win_p.add_argument(
        "--no-minimized",
        action="store_true",
        help="Exclude minimized windows.",
    )

    shot_p = subparsers.add_parser("shot", help="Capture a screenshot observation.")
    shot_p.add_argument("--target", default="screen", help="Capture target.")
    shot_p.add_argument("--grid", action="store_true", help="Draw coordinate grid.")
    shot_p.add_argument(
        "--no-cursor",
        action="store_true",
        help="Do not draw cursor crosshair on preview.",
    )
    shot_p.add_argument("--max-edge", type=int, default=None, help="Preview max edge.")
    shot_p.add_argument(
        "--restore",
        action="store_true",
        help="Restore minimized target window before capture.",
    )

    zoom_p = subparsers.add_parser("zoom", help="Zoom into an existing observation.")
    zoom_p.add_argument("--obs", required=True, help="Parent observation ID.")
    zoom_p.add_argument("--x", type=float, required=True, help="Region left.")
    zoom_p.add_argument("--y", type=float, required=True, help="Region top.")
    zoom_p.add_argument("--w", type=float, required=True, help="Region width.")
    zoom_p.add_argument("--h", type=float, required=True, help="Region height.")
    zoom_p.add_argument(
        "--norm1000",
        action="store_true",
        help="Interpret x, y, w, h in [0, 1000] normalized coordinates.",
    )
    zoom_p.add_argument("--fresh", action="store_true", help="Re-capture region via GDI.")
    zoom_p.add_argument("--factor", type=float, default=None, help="Zoom scale factor.")
    return parser


def _dispatch(args: argparse.Namespace) -> Result | None:
    if args.command == "doctor":
        return Edm.build_default().doctor()
    if args.command == "monitors":
        return Edm.build_default().list_monitors()
    if args.command == "windows":
        return Edm.build_default().list_windows(
            query=args.query,
            include_minimized=not args.no_minimized,
        )
    if args.command == "shot":
        return Edm.build_default().screenshot(
            target=args.target,
            max_edge=args.max_edge,
            grid=args.grid,
            cursor=not args.no_cursor,
            restore=args.restore,
        )
    if args.command == "zoom":
        return Edm.build_default().zoom(
            observation_id=args.obs,
            x=args.x,
            y=args.y,
            w=args.w,
            h=args.h,
            coord_space="norm1000" if args.norm1000 else "pixel",
            fresh=args.fresh,
            factor=args.factor,
        )
    return None


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

    if args.command is not None:
        ensure_dpi_awareness()
        try:
            result = _dispatch(args)
        except EdmError as exc:
            print(json.dumps(exc.to_payload(), ensure_ascii=False), file=sys.stderr)
            return 2
        if result is not None:
            print(json.dumps(result.payload, ensure_ascii=False))
            return 0

    parser.print_help()
    return 0
