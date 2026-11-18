"""Validated multi-step action sequence execution."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from edm.actions.addressing import Address, resolve_point
from edm.actions.keys import parse_chord
from edm.capture.select import parse_target
from edm.errors import EdmError, ErrorCode

if TYPE_CHECKING:
    from edm.service import Edm, Result

ALLOWED_STEP_TOOLS: frozenset[str] = frozenset(
    {
        "click",
        "move_mouse",
        "drag",
        "draw_path",
        "mouse_button",
        "key_state",
        "scroll",
        "type_text",
        "press_keys",
        "wait_for",
    }
)

_MAX_STEPS = 25


@dataclass(frozen=True)
class Step:
    """Single step in a ``run_sequence`` batch."""

    tool: str
    args: dict[str, Any]


def _address_from_args(args: dict[str, Any]) -> Address:
    return Address(
        observation_id=args.get("observation_id"),
        x=args.get("x"),
        y=args.get("y"),
        coord_space=args.get("coord_space", "pixel"),
        mark=args.get("mark"),
        text=args.get("text"),
        target=args.get("target", "screen"),
        screen_x=args.get("screen_x"),
        screen_y=args.get("screen_y"),
    )


def _sub_address(raw: Any, label: str) -> Address:
    if isinstance(raw, Address):
        return raw
    if isinstance(raw, dict):
        return _address_from_args(raw)
    raise EdmError(
        ErrorCode.INVALID_ARGUMENT,
        f"Expected Address or dict for {label}.",
    )


def parse_steps(raw_steps: Sequence[Step | dict[str, Any]]) -> list[Step]:
    """Normalize and count-check a sequence of steps (1..25)."""
    if not raw_steps or len(raw_steps) > _MAX_STEPS:
        raise EdmError(
            ErrorCode.INVALID_ARGUMENT,
            f"run_sequence requires 1 to {_MAX_STEPS} steps, got {len(raw_steps)}.",
            details={"count": len(raw_steps)},
        )
    steps: list[Step] = []
    for idx, item in enumerate(raw_steps):
        if isinstance(item, Step):
            steps.append(item)
        elif isinstance(item, dict):
            tool = item.get("tool")
            args = item.get("args", {})
            if not isinstance(tool, str) or not isinstance(args, dict):
                raise EdmError(
                    ErrorCode.INVALID_ARGUMENT,
                    f"Step {idx} must have string 'tool' and dict 'args'.",
                    details={"index": idx},
                )
            steps.append(Step(tool=tool, args=dict(args)))
        else:
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"Invalid step type at index {idx}.",
                details={"index": idx},
            )
    return steps


def validate_steps(edm: Edm, steps: list[Step]) -> None:
    """Pre-validate every step before acquiring locks or sending input."""
    for idx, step in enumerate(steps):
        if step.tool not in ALLOWED_STEP_TOOLS:
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"Step {idx} tool {step.tool!r} is not allowed in run_sequence.",
                details={"index": idx, "tool": step.tool},
            )
        args = step.args
        if step.tool in ("click", "move_mouse", "scroll"):
            resolve_point(edm, _address_from_args(args))
            if step.tool == "click":
                count = args.get("count", 1)
                if not isinstance(count, int) or count < 1:
                    raise EdmError(ErrorCode.INVALID_ARGUMENT, "click count must be >= 1.")
                mods = args.get("modifiers")
                if mods:
                    parse_chord("+".join(mods))
        elif step.tool == "drag":
            from_addr = _sub_address(args.get("from_addr", args.get("from")), "from_addr")
            to_addr = _sub_address(args.get("to_addr", args.get("to")), "to_addr")
            resolve_point(edm, from_addr)
            resolve_point(edm, to_addr)
        elif step.tool == "draw_path":
            obs_id = args.get("observation_id")
            pts = args.get("points")
            if (
                not isinstance(obs_id, str)
                or not isinstance(pts, list)
                or not (1 <= len(pts) <= 200)
            ):
                raise EdmError(
                    ErrorCode.INVALID_ARGUMENT,
                    f"Step {idx} draw_path requires observation_id and 1..200 points.",
                )
            obs = edm.store.get(obs_id)
            space = args.get("coord_space", "pixel")
            for p in pts:
                obs.mapping.to_screen(float(p[0]), float(p[1]), space)
        elif step.tool == "mouse_button":
            if args.get("action") not in ("down", "up"):
                raise EdmError(ErrorCode.INVALID_ARGUMENT, "mouse_button action must be down/up.")
            if args.get("addr") is not None:
                resolve_point(edm, _sub_address(args["addr"], "addr"))
        elif step.tool == "key_state":
            if args.get("action") not in ("down", "up"):
                raise EdmError(ErrorCode.INVALID_ARGUMENT, "key_state action must be down/up.")
            vks = parse_chord(str(args.get("key", "")))
            if len(vks) != 1:
                raise EdmError(ErrorCode.INVALID_ARGUMENT, "key_state requires a single key.")
        elif step.tool == "type_text":
            if not isinstance(args.get("text"), str):
                raise EdmError(ErrorCode.INVALID_ARGUMENT, "type_text requires string 'text'.")
        elif step.tool == "press_keys":
            keys = args.get("keys")
            seq = [keys] if isinstance(keys, str) else list(keys or [])
            if not seq:
                raise EdmError(ErrorCode.INVALID_ARGUMENT, "press_keys requires non-empty 'keys'.")
            for ch in seq:
                parse_chord(ch)
        elif step.tool == "wait_for":
            kind = args.get("kind")
            timeout_s = float(args.get("timeout_s", 10.0))
            if not math.isfinite(timeout_s) or timeout_s <= 0 or timeout_s > 60.0:
                raise EdmError(ErrorCode.INVALID_ARGUMENT, "wait_for timeout_s must be in (0, 60].")
            if kind == "text":
                raise EdmError(ErrorCode.DEPENDENCY_MISSING, "wait_for text requires T4.2 OCR.")
            if kind in ("window", "window_gone"):
                if not args.get("query"):
                    raise EdmError(ErrorCode.INVALID_ARGUMENT, f"wait_for {kind} requires query.")
            elif kind in ("change", "stable"):
                parse_target(str(args.get("target", "screen")))
            else:
                raise EdmError(ErrorCode.INVALID_ARGUMENT, f"Unsupported wait_for kind: {kind!r}")


def _run_step(edm: Edm, step: Step) -> None:
    a = step.args
    t = step.tool
    if t == "click":
        edm.click(
            _address_from_args(a),
            button=a.get("button", "left"),
            count=a.get("count", 1),
            modifiers=a.get("modifiers"),
            verify=a.get("verify", True),
            observe=False,
        )
    elif t == "move_mouse":
        edm.move_mouse(_address_from_args(a), verify=a.get("verify", True), observe=False)
    elif t == "drag":
        edm.drag(
            _sub_address(a.get("from_addr", a.get("from")), "from_addr"),
            _sub_address(a.get("to_addr", a.get("to")), "to_addr"),
            button=a.get("button", "left"),
            duration_ms=a.get("duration_ms", 300),
            verify=a.get("verify", True),
            observe=False,
        )
    elif t == "draw_path":
        pts = [(float(p[0]), float(p[1])) for p in a["points"]]
        edm.draw_path(
            a["observation_id"],
            pts,
            coord_space=a.get("coord_space", "pixel"),
            button=a.get("button", "left"),
            press_button=a.get("press_button", True),
            smooth=a.get("smooth", False),
            duration_ms=a.get("duration_ms", 600),
            observe=False,
        )
    elif t == "mouse_button":
        addr = _sub_address(a["addr"], "addr") if a.get("addr") is not None else None
        edm.mouse_button(a["action"], button=a.get("button", "left"), addr=addr, observe=False)
    elif t == "key_state":
        edm.key_state(a["key"], a["action"], observe=False)
    elif t == "scroll":
        edm.scroll(
            _address_from_args(a),
            dy=a.get("dy", 0),
            dx=a.get("dx", 0),
            verify=a.get("verify", True),
            observe=False,
        )
    elif t == "type_text":
        edm.type_text(a["text"], interval_ms=a.get("interval_ms", 0), observe=False)
    elif t == "press_keys":
        edm.press_keys(a["keys"], repeat=a.get("repeat", 1), observe=False)
    elif t == "wait_for":
        edm.wait_for(
            a["kind"],
            target=a.get("target", "screen"),
            query=a.get("query"),
            timeout_s=a.get("timeout_s", 10.0),
            observe=False,
        )


def execute_sequence(
    edm: Edm,
    raw_steps: Sequence[Step | dict[str, Any]],
    stop_on_error: bool = True,
) -> Result:
    """Validate and execute a multi-step sequence under a single input lock."""
    from edm.service import Result

    steps = parse_steps(raw_steps)
    validate_steps(edm, steps)

    step_results: list[dict[str, Any]] = []
    completed = 0
    last_error: dict[str, Any] | None = None
    aborted = False

    with edm.guard.input_lock():
        try:
            for idx, step in enumerate(steps):
                if edm.killswitch.triggered():
                    err_obj = EdmError(
                        ErrorCode.ABORTED_BY_USER,
                        "Sequence aborted by user kill switch.",
                    ).to_payload()["error"]
                    step_results.append(
                        {"index": idx, "tool": step.tool, "ok": False, "error": err_obj}
                    )
                    last_error = err_obj
                    aborted = True
                    break

                try:
                    _run_step(edm, step)
                    step_results.append({"index": idx, "tool": step.tool, "ok": True})
                    completed += 1
                except EdmError as exc:
                    err_obj = exc.to_payload()["error"]
                    step_results.append(
                        {"index": idx, "tool": step.tool, "ok": False, "error": err_obj}
                    )
                    last_error = err_obj
                    if exc.code == ErrorCode.ABORTED_BY_USER:
                        aborted = True
                        break
                    if stop_on_error:
                        break
        finally:
            edm.input_sink.release_held()

    if aborted or (last_error is not None and stop_on_error):
        return Result(
            payload={
                "ok": False,
                "action": "run_sequence",
                "error": last_error,
                "details": {"steps": step_results, "completed": completed},
                "warnings": [],
            }
        )

    shot = edm.screenshot(target="screen")
    return Result(
        payload={
            "ok": True,
            "action": "run_sequence",
            "observation": shot.payload["observation"],
            "details": {"steps": step_results, "completed": completed},
            "warnings": [],
        },
        image=shot.image,
        mime=shot.mime,
    )
