"""Command-line interface for EDM."""

from __future__ import annotations

import argparse
import json
import sys

from edm import __version__
from edm.actions.addressing import Address
from edm.errors import EdmError, ErrorCode
from edm.geometry import Rect
from edm.service import Edm, Result
from edm.win32.dpi import ensure_dpi_awareness


def _add_address_args(p: argparse.ArgumentParser, prefix: str = "") -> None:
    p.add_argument(f"--{prefix}obs", default=None, help="Observation ID.")
    p.add_argument(f"--{prefix}x", type=float, default=None, help="X coordinate.")
    p.add_argument(f"--{prefix}y", type=float, default=None, help="Y coordinate.")
    p.add_argument(
        f"--{prefix}norm1000",
        action="store_true",
        help="Interpret coordinates in [0, 1000].",
    )
    p.add_argument(f"--{prefix}mark", type=int, default=None, help="Set-of-Mark ID.")
    p.add_argument(f"--{prefix}text", default=None, help="OCR text query.")
    p.add_argument(
        f"--{prefix}screen",
        nargs=2,
        type=int,
        metavar=("X", "Y"),
        default=None,
        help="Raw screen X Y coordinates.",
    )


def _extract_address(args: argparse.Namespace, prefix: str = "") -> Address:
    key_prefix = prefix.replace("-", "_")
    obs = getattr(args, f"{key_prefix}obs")
    x = getattr(args, f"{key_prefix}x")
    y = getattr(args, f"{key_prefix}y")
    norm1000 = getattr(args, f"{key_prefix}norm1000")
    mark = getattr(args, f"{key_prefix}mark")
    text = getattr(args, f"{key_prefix}text")
    screen = getattr(args, f"{key_prefix}screen")
    return Address(
        observation_id=obs,
        x=x,
        y=y,
        coord_space="norm1000" if norm1000 else "pixel",
        mark=mark,
        text=text,
        screen_x=screen[0] if screen is not None else None,
        screen_y=screen[1] if screen is not None else None,
    )


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
    win_p.add_argument("--no-minimized", action="store_true", help="Exclude minimized windows.")

    shot_p = subparsers.add_parser("shot", help="Capture a screenshot observation.")
    shot_p.add_argument("--target", default="screen", help="Capture target.")
    shot_p.add_argument("--grid", action="store_true", help="Draw coordinate grid.")
    shot_p.add_argument("--no-cursor", action="store_true", help="Omit cursor crosshair.")
    shot_p.add_argument("--max-edge", type=int, default=None, help="Preview max edge.")
    shot_p.add_argument("--restore", action="store_true", help="Restore minimized window.")

    zoom_p = subparsers.add_parser("zoom", help="Zoom into an existing observation.")
    zoom_p.add_argument("--obs", required=True, help="Parent observation ID.")
    zoom_p.add_argument("--x", type=float, required=True, help="Region left.")
    zoom_p.add_argument("--y", type=float, required=True, help="Region top.")
    zoom_p.add_argument("--w", type=float, required=True, help="Region width.")
    zoom_p.add_argument("--h", type=float, required=True, help="Region height.")
    zoom_p.add_argument("--norm1000", action="store_true", help="Normalized [0, 1000] coords.")
    zoom_p.add_argument("--fresh", action="store_true", help="Re-capture region via GDI.")
    zoom_p.add_argument("--factor", type=float, default=None, help="Zoom scale factor.")

    click_p = subparsers.add_parser("click", help="Click at an addressed point.")
    _add_address_args(click_p)
    click_p.add_argument("--button", default="left", choices=["left", "right", "middle"])
    click_p.add_argument("--count", type=int, default=1)
    click_p.add_argument("--no-verify", action="store_true")
    click_p.add_argument("--no-observe", action="store_true")

    move_p = subparsers.add_parser("move", help="Move mouse cursor to an addressed point.")
    _add_address_args(move_p)
    move_p.add_argument("--no-observe", action="store_true")

    drag_p = subparsers.add_parser("drag", help="Drag between two addressed points.")
    _add_address_args(drag_p, prefix="from-")
    _add_address_args(drag_p, prefix="to-")
    drag_p.add_argument("--button", default="left", choices=["left", "right", "middle"])
    drag_p.add_argument("--duration-ms", type=int, default=300)
    drag_p.add_argument("--no-observe", action="store_true")

    dp_p = subparsers.add_parser("draw-path", help="Draw along a JSON list of [x, y] points.")
    dp_p.add_argument("--obs", required=True, help="Observation ID.")
    dp_p.add_argument("--points", required=True, help="JSON list of [x, y] pairs.")
    dp_p.add_argument("--norm1000", action="store_true")
    dp_p.add_argument("--button", default="left", choices=["left", "right", "middle"])
    dp_p.add_argument("--no-press", action="store_true")
    dp_p.add_argument("--smooth", action="store_true")
    dp_p.add_argument("--duration-ms", type=int, default=600)
    dp_p.add_argument("--no-observe", action="store_true")

    mb_p = subparsers.add_parser("mouse-btn", help="Press or release a mouse button.")
    mb_p.add_argument("action", choices=["down", "up"])
    mb_p.add_argument("--button", default="left", choices=["left", "right", "middle"])
    mb_p.add_argument("--no-observe", action="store_true")

    ks_p = subparsers.add_parser("key-state", help="Press or release a single key.")
    ks_p.add_argument("key", help="Key name or single character.")
    ks_p.add_argument("action", choices=["down", "up"])
    ks_p.add_argument("--no-observe", action="store_true")

    sc_p = subparsers.add_parser("scroll", help="Scroll mouse wheel at an addressed point.")
    _add_address_args(sc_p)
    sc_p.add_argument("--dy", type=int, default=0)
    sc_p.add_argument("--dx", type=int, default=0)
    sc_p.add_argument("--no-observe", action="store_true")

    tp_p = subparsers.add_parser("type", help="Type Unicode text.")
    tp_p.add_argument("--text", required=True, help="Text to type.")
    tp_p.add_argument("--interval-ms", type=int, default=0)
    tp_p.add_argument("--no-observe", action="store_true")

    ky_p = subparsers.add_parser("keys", help="Press one or more key chords.")
    ky_p.add_argument("chords", nargs="+", help="Key chord(s), e.g. ctrl+s.")
    ky_p.add_argument("--repeat", type=int, default=1)
    ky_p.add_argument("--no-observe", action="store_true")

    wa_p = subparsers.add_parser("window", help="Perform a window management action.")
    wa_p.add_argument("target", help="Window query selector.")
    wa_p.add_argument(
        "action",
        choices=["focus", "minimize", "maximize", "restore", "close", "move", "resize"],
    )
    wa_p.add_argument("--rect", nargs=4, type=int, metavar=("X", "Y", "W", "H"), default=None)
    wa_p.add_argument("--no-observe", action="store_true")

    ln_p = subparsers.add_parser("launch", help="Launch an application or URL.")
    ln_p.add_argument("target", help="Path, URL, Start Menu shortcut, or app name.")
    ln_p.add_argument("--args", nargs="*", default=None)
    ln_p.add_argument("--wait-window", default=None)
    ln_p.add_argument("--timeout-s", type=float, default=30.0)
    ln_p.add_argument("--no-observe", action="store_true")

    wt_p = subparsers.add_parser("wait", help="Wait for a screen or window condition.")
    wt_p.add_argument("kind", choices=["change", "stable", "window", "window_gone", "text"])
    wt_p.add_argument("--target", default="screen")
    wt_p.add_argument("--query", default=None)
    wt_p.add_argument("--timeout-s", type=float, default=10.0)

    cl_p = subparsers.add_parser("clip", help="Get or set clipboard text.")
    cl_p.add_argument("op", choices=["get", "set"])
    cl_p.add_argument("--text", default=None)

    sq_p = subparsers.add_parser("seq", help="Execute a JSON sequence of steps.")
    sq_p.add_argument("--steps", required=True, help="JSON list of {tool, args} steps.")
    sq_p.add_argument("--continue-on-error", action="store_true")

    return parser


def _dispatch(args: argparse.Namespace) -> Result | None:
    edm = Edm.build_default()
    if args.command == "doctor":
        return edm.doctor()
    if args.command == "monitors":
        return edm.list_monitors()
    if args.command == "windows":
        return edm.list_windows(query=args.query, include_minimized=not args.no_minimized)
    if args.command == "shot":
        return edm.screenshot(
            target=args.target,
            max_edge=args.max_edge,
            grid=args.grid,
            cursor=not args.no_cursor,
            restore=args.restore,
        )
    if args.command == "zoom":
        return edm.zoom(
            observation_id=args.obs,
            x=args.x,
            y=args.y,
            w=args.w,
            h=args.h,
            coord_space="norm1000" if args.norm1000 else "pixel",
            fresh=args.fresh,
            factor=args.factor,
        )
    if args.command == "click":
        return edm.click(
            _extract_address(args),
            button=args.button,
            count=args.count,
            verify=not args.no_verify,
            observe=not args.no_observe,
        )
    if args.command == "move":
        return edm.move_mouse(_extract_address(args), observe=not args.no_observe)
    if args.command == "drag":
        return edm.drag(
            _extract_address(args, prefix="from-"),
            _extract_address(args, prefix="to-"),
            button=args.button,
            duration_ms=args.duration_ms,
            observe=not args.no_observe,
        )
    if args.command == "draw-path":
        try:
            raw_pts = json.loads(args.points)
        except json.JSONDecodeError as exc:
            raise EdmError(ErrorCode.INVALID_ARGUMENT, f"Invalid JSON points: {exc}") from exc
        if not isinstance(raw_pts, list):
            raise EdmError(ErrorCode.INVALID_ARGUMENT, "points must be a JSON list of [x, y].")
        pts = [(float(p[0]), float(p[1])) for p in raw_pts]
        return edm.draw_path(
            args.obs,
            pts,
            coord_space="norm1000" if args.norm1000 else "pixel",
            button=args.button,
            press_button=not args.no_press,
            smooth=args.smooth,
            duration_ms=args.duration_ms,
            observe=not args.no_observe,
        )
    if args.command == "mouse-btn":
        return edm.mouse_button(args.action, button=args.button, observe=not args.no_observe)
    if args.command == "key-state":
        return edm.key_state(args.key, args.action, observe=not args.no_observe)
    if args.command == "scroll":
        return edm.scroll(
            _extract_address(args),
            dy=args.dy,
            dx=args.dx,
            observe=not args.no_observe,
        )
    if args.command == "type":
        return edm.type_text(args.text, interval_ms=args.interval_ms, observe=not args.no_observe)
    if args.command == "keys":
        chords = args.chords[0] if len(args.chords) == 1 else args.chords
        return edm.press_keys(chords, repeat=args.repeat, observe=not args.no_observe)
    if args.command == "window":
        rect = Rect.from_xywh(*args.rect) if args.rect is not None else None
        return edm.window_action(
            args.target,
            args.action,
            rect=rect,
            observe=not args.no_observe,
        )
    if args.command == "launch":
        return edm.launch(
            args.target,
            args=args.args,
            wait_window=args.wait_window,
            timeout_s=args.timeout_s,
            observe=not args.no_observe,
        )
    if args.command == "wait":
        return edm.wait_for(
            args.kind,
            target=args.target,
            query=args.query,
            timeout_s=args.timeout_s,
        )
    if args.command == "clip":
        return edm.clipboard(args.op, text=args.text)
    if args.command == "seq":
        try:
            raw_steps = json.loads(args.steps)
        except json.JSONDecodeError as exc:
            raise EdmError(ErrorCode.INVALID_ARGUMENT, f"Invalid JSON steps: {exc}") from exc
        if not isinstance(raw_steps, list):
            raise EdmError(ErrorCode.INVALID_ARGUMENT, "steps must be a JSON list.")
        return edm.run_sequence(raw_steps, stop_on_error=not args.continue_on_error)
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
