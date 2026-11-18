"""Wait primitives, settle detection, and stale observation checks."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from PIL import Image

from edm.errors import EdmError, ErrorCode
from edm.geometry import Point, Rect
from edm.observe.diff import patch_diff
from edm.observe.store import Observation

if TYPE_CHECKING:
    from edm.service import Edm

_STABLE_DIFF_THRESHOLD = 0.002


def wait_until(
    pred: Callable[[], bool],
    timeout_s: float,
    interval_s: float = 0.2,
) -> bool:
    """Poll *pred* until it returns True or *timeout_s* elapses."""
    deadline = time.monotonic() + max(0.0, timeout_s)
    while True:
        if pred():
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(interval_s, remaining))


def wait_for_stable(
    grab: Callable[[], Image.Image],
    quiet_ms: int,
    timeout_ms: int,
) -> Image.Image:
    """Wait until consecutive frames differ by < 0.002 for *quiet_ms* (capped at *timeout_ms*)."""
    start = time.monotonic()
    timeout_s = max(0.0, timeout_ms / 1000.0)
    quiet_s = max(0.0, quiet_ms / 1000.0)
    prev = grab()
    if quiet_s <= 0 or timeout_s <= 0:
        return prev

    quiet_since: float | None = None
    poll_s = min(0.05, max(0.01, quiet_s / 3.0))
    while time.monotonic() - start < timeout_s:
        time.sleep(poll_s)
        curr = grab()
        if patch_diff(prev, curr) < _STABLE_DIFF_THRESHOLD:
            if quiet_since is None:
                quiet_since = time.monotonic()
            if time.monotonic() - quiet_since >= quiet_s:
                return curr
        else:
            quiet_since = None
        prev = curr
    return prev


def check_stale(
    edm: Edm,
    obs: Observation,
    point: Point,
    verify: bool = True,
) -> None:
    """Verify *obs* is still fresh at *point*, raising ``STALE_OBSERVATION`` if not."""
    if edm.clock() - obs.created_at > edm.cfg.observation_ttl_s:
        raise EdmError(
            ErrorCode.STALE_OBSERVATION,
            f"Observation {obs.id} has expired.",
            details={"observation_id": obs.id},
        )

    if obs.window is not None:
        hwnd = int(obs.window["hwnd"])
        try:
            cur = edm.window_info(hwnd)
        except EdmError as exc:
            raise EdmError(
                ErrorCode.STALE_OBSERVATION,
                f"Target window hwnd={hwnd} is no longer available.",
                details={"hwnd": hwnd, "observation_id": obs.id},
            ) from exc

        if cur.rect.as_list() != obs.window.get("rect") or cur.title != obs.window.get("title"):
            raise EdmError(
                ErrorCode.STALE_OBSERVATION,
                f"Window hwnd={hwnd} moved, resized, or changed title since observation.",
                details={"hwnd": hwnd, "observation_id": obs.id},
            )

        popup = edm.last_active_popup(hwnd)
        prev_popup = int(obs.window.get("last_popup", hwnd))
        if popup != 0 and popup != hwnd and popup != prev_popup:
            raise EdmError(
                ErrorCode.STALE_OBSERVATION,
                f"A modal popup (hwnd={popup}) appeared over window hwnd={hwnd}.",
                details={"hwnd": hwnd, "popup_hwnd": popup, "observation_id": obs.id},
            )

    if verify:
        patch_sz = edm.cfg.stale_patch_px
        half = patch_sz // 2
        patch_rect = Rect.from_xywh(point.x - half, point.y - half, patch_sz, patch_sz)
        clipped = patch_rect.intersection(obs.frame_rect)
        if clipped is not None:
            gdi = edm.capture_backends.get("gdi")
            if gdi is not None and gdi.available()[0]:
                orig = edm.store.load_original(obs)
                local_box = (
                    clipped.left - obs.frame_rect.left,
                    clipped.top - obs.frame_rect.top,
                    clipped.right - obs.frame_rect.left,
                    clipped.bottom - obs.frame_rect.top,
                )
                old_patch = orig.crop(local_box)
                new_patch = gdi.capture_rect(clipped).image
                diff = patch_diff(old_patch, new_patch)
                if diff > edm.cfg.stale_threshold:
                    raise EdmError(
                        ErrorCode.STALE_OBSERVATION,
                        f"Screen patch around ({point.x}, {point.y}) changed ({diff:.3f}).",
                        details={"observation_id": obs.id, "diff": diff},
                    )
