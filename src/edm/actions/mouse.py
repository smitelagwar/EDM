"""Mouse event generation, absolute normalization, and path interpolation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from edm.errors import EdmError, ErrorCode
from edm.geometry import Point, Rect

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x1000
MOUSEEVENTF_VIRTUALDESK = 0x4000
MOUSEEVENTF_ABSOLUTE = 0x8000

WHEEL_DELTA = 120

_BUTTON_FLAGS: dict[str, tuple[int, int]] = {
    "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
    "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
    "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
}


@dataclass(frozen=True)
class MouseEvent:
    """Low-level mouse event ready for ``SendInput``."""

    flags: int
    dx: int = 0
    dy: int = 0
    data: int = 0


def normalize_abs(p: Point, virtual: Rect) -> tuple[int, int]:
    """Normalize physical screen point *p* into ``[0, 65535]`` virtual desktop coordinates."""
    span_x = max(1, virtual.width - 1)
    span_y = max(1, virtual.height - 1)
    nx = round((p.x - virtual.left) * 65535 / span_x)
    ny = round((p.y - virtual.top) * 65535 / span_y)
    return (max(0, min(65535, nx)), max(0, min(65535, ny)))


def mouse_button_events(button: str, action: Literal["down", "up"]) -> list[MouseEvent]:
    """Generate a mouse button down or up event."""
    pair = _BUTTON_FLAGS.get(button)
    if pair is None:
        raise EdmError(
            ErrorCode.INVALID_ARGUMENT,
            f"Unsupported mouse button: {button!r}",
            details={"button": button},
        )
    if action == "down":
        return [MouseEvent(flags=pair[0])]
    if action == "up":
        return [MouseEvent(flags=pair[1])]
    raise EdmError(
        ErrorCode.INVALID_ARGUMENT,
        f"Invalid mouse button action: {action!r}",
        details={"action": action},
    )


def click_events(button: str, count: int = 1) -> list[MouseEvent]:
    """Generate *count* click (down + up) pairs for *button*."""
    if count < 1:
        raise EdmError(
            ErrorCode.INVALID_ARGUMENT,
            f"Click count must be >= 1, got {count}.",
            details={"count": count},
        )
    pair = mouse_button_events(button, "down") + mouse_button_events(button, "up")
    return pair * count


def wheel_events(dy: int = 0, dx: int = 0) -> list[MouseEvent]:
    """Generate vertical and horizontal wheel events in multiples of ``WHEEL_DELTA``."""
    events: list[MouseEvent] = []
    if dy != 0:
        events.append(MouseEvent(flags=MOUSEEVENTF_WHEEL, data=dy * WHEEL_DELTA))
    if dx != 0:
        events.append(MouseEvent(flags=MOUSEEVENTF_HWHEEL, data=dx * WHEEL_DELTA))
    return events


def _catmull_rom(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
    t2 = t * t
    t3 = t2 * t
    return 0.5 * (
        (2.0 * p1)
        + (-p0 + p2) * t
        + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2
        + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3
    )


def interpolate_path(
    points: Sequence[Point],
    *,
    smooth: bool = False,
    steps_per_segment: int = 6,
) -> list[Point]:
    """Interpolate a sequence of points linearly or with Catmull-Rom splines."""
    if steps_per_segment < 1:
        raise EdmError(
            ErrorCode.INVALID_ARGUMENT,
            f"steps_per_segment must be >= 1, got {steps_per_segment}.",
        )
    if not points:
        return []
    if len(points) == 1:
        return [points[0]]

    out: list[Point] = []
    n = len(points)
    for i in range(n - 1):
        p1 = points[i]
        p2 = points[i + 1]
        p0 = points[i - 1] if i > 0 else p1
        p3 = points[i + 2] if i + 2 < n else p2
        for step in range(steps_per_segment):
            t = step / steps_per_segment
            if smooth:
                x = round(_catmull_rom(p0.x, p1.x, p2.x, p3.x, t))
                y = round(_catmull_rom(p0.y, p1.y, p2.y, p3.y, t))
            else:
                x = round(p1.x + (p2.x - p1.x) * t)
                y = round(p1.y + (p2.y - p1.y) * t)
            pt = Point(x, y)
            if not out or out[-1] != pt:
                out.append(pt)
    if not out or out[-1] != points[-1]:
        out.append(points[-1])
    return out
