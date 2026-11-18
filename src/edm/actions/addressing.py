"""Unified addressing validation and screen-point resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from edm.errors import EdmError, ErrorCode
from edm.geometry import CoordSpace, Point
from edm.observe.store import Observation

if TYPE_CHECKING:
    from edm.service import Edm

AddressMode = Literal["obs", "mark", "text", "screen"]


@dataclass(frozen=True)
class Address:
    """Target address specifying exactly one of obs+xy, obs+mark, text, or screen_xy."""

    observation_id: str | None = None
    x: float | None = None
    y: float | None = None
    coord_space: CoordSpace = "pixel"
    mark: int | None = None
    text: str | None = None
    target: str = "screen"
    screen_x: int | None = None
    screen_y: int | None = None


def validate_address(a: Address) -> AddressMode:
    """Validate that *a* specifies exactly one addressing mode and return it."""
    has_obs = a.observation_id is not None and a.x is not None and a.y is not None
    has_mark = a.observation_id is not None and a.mark is not None
    has_text = a.text is not None
    has_screen = a.screen_x is not None and a.screen_y is not None

    # Reject partial / dangling fields
    if (a.x is not None or a.y is not None) and not has_obs:
        raise EdmError(
            ErrorCode.INVALID_ARGUMENT,
            "x and y require observation_id and both coordinates.",
        )
    if a.mark is not None and not has_mark:
        raise EdmError(
            ErrorCode.INVALID_ARGUMENT,
            "mark requires observation_id.",
        )
    if (a.screen_x is None) != (a.screen_y is None):
        raise EdmError(
            ErrorCode.INVALID_ARGUMENT,
            "screen_x and screen_y must be provided together.",
        )
    if a.observation_id is not None and not (has_obs or has_mark):
        raise EdmError(
            ErrorCode.INVALID_ARGUMENT,
            "observation_id requires either (x, y) or mark.",
        )

    modes: list[AddressMode] = []
    if has_obs:
        modes.append("obs")
    if has_mark:
        modes.append("mark")
    if has_text:
        modes.append("text")
    if has_screen:
        modes.append("screen")

    if len(modes) != 1:
        raise EdmError(
            ErrorCode.INVALID_ARGUMENT,
            "Address must specify exactly one mode (obs+xy, obs+mark, text, or screen_xy).",
            details={"modes": modes},
        )
    return modes[0]


def resolve_point(
    edm: Edm,
    a: Address,
) -> tuple[Point, Observation | None, list[str]]:
    """Resolve *a* into ``(screen_point, observation_or_none, warnings)``."""
    mode = validate_address(a)
    if mode == "obs":
        assert a.observation_id is not None and a.x is not None and a.y is not None
        obs = edm.store.get(a.observation_id)
        pt = obs.mapping.to_screen(a.x, a.y, a.coord_space)
        return pt, obs, []

    if mode == "mark":
        assert a.observation_id is not None and a.mark is not None
        obs = edm.store.get(a.observation_id)
        for m in obs.marks:
            if m.id == a.mark:
                return m.rect.center, obs, []
        raise EdmError(
            ErrorCode.INVALID_ARGUMENT,
            f"Mark {a.mark} not found in observation {obs.id}.",
            details={"observation_id": obs.id, "mark": a.mark},
        )

    if mode == "text":
        assert a.text is not None
        res = edm.find_text(a.text, target=a.target, match="contains")
        matches = res.payload["details"]["matches"]
        if not matches:
            raise EdmError(
                ErrorCode.WINDOW_NOT_FOUND,
                f"Text {a.text!r} not found in target {a.target!r}.",
                details={"text": a.text, "target": a.target},
            )
        first = matches[0]
        rs = first["rect_screen"]
        pt = Point((rs[0] + rs[2]) // 2, (rs[1] + rs[3]) // 2)
        warnings: list[str] = []
        if len(matches) > 1:
            warnings.append(
                f"Multiple OCR matches ({len(matches)}) for {a.text!r}; selected first."
            )
        obs = edm.store.get(res.payload["observation"]["id"])
        return pt, obs, warnings

    assert a.screen_x is not None and a.screen_y is not None
    return (
        Point(a.screen_x, a.screen_y),
        None,
        ["Using raw screen coordinates bypasses observation stale protection."],
    )
