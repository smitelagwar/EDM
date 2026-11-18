"""Target parsing and backend selection strategy for screen/window capture."""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from dataclasses import dataclass
from typing import Literal

from edm.capture.base import CaptureBackend, Frame, is_blank
from edm.capture.occlusion import visible_fraction
from edm.config import Config
from edm.errors import EdmError, ErrorCode
from edm.geometry import Rect
from edm.win32.api import user32
from edm.win32.monitors import list_monitors, virtual_screen
from edm.win32.windows import WindowInfo, resolve_window, root_window_at, window_info

_SW_RESTORE = 9

_ShowWindow = user32.ShowWindow
_ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
_ShowWindow.restype = wintypes.BOOL

_OCCLUSION_THRESHOLD = 0.98


def _restore_window(hwnd: int) -> None:
    _ShowWindow(hwnd, _SW_RESTORE)
    time.sleep(0.15)


@dataclass(frozen=True)
class CaptureTarget:
    """Parsed capture target specification."""

    kind: Literal["screen", "monitor", "window", "region"]
    monitor: int | None = None
    query: str | None = None
    rect: Rect | None = None


def parse_target(s: str) -> CaptureTarget:
    """Parse a target string (``screen``, ``monitor:N``, ``window:Q``, ``region:x,y,w,h``)."""
    stripped = s.strip()
    if not stripped:
        raise EdmError(ErrorCode.INVALID_ARGUMENT, "Capture target must not be empty.")
    if stripped == "screen":
        return CaptureTarget(kind="screen")

    if stripped.startswith("monitor:"):
        raw = stripped[8:].strip()
        try:
            idx = int(raw)
        except ValueError as exc:
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"Invalid monitor index: {raw!r}",
            ) from exc
        if idx < 0:
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"Monitor index must be non-negative: {idx}",
            )
        return CaptureTarget(kind="monitor", monitor=idx)

    if stripped.startswith("window:"):
        query = stripped[7:].strip()
        if not query:
            raise EdmError(ErrorCode.INVALID_ARGUMENT, "Window target query must not be empty.")
        return CaptureTarget(kind="window", query=query)

    if stripped.startswith("region:"):
        raw = stripped[7:].strip()
        parts = [p.strip() for p in raw.split(",")]
        if len(parts) != 4:
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"Region target must have 4 comma-separated integers (x,y,w,h): {raw!r}",
            )
        try:
            x, y, w, h = (int(p) for p in parts)
        except ValueError as exc:
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"Invalid region coordinates: {raw!r}",
            ) from exc
        if w <= 0 or h <= 0:
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"Region width and height must be positive: {(w, h)}",
            )
        return CaptureTarget(kind="region", rect=Rect.from_xywh(x, y, w, h))

    raise EdmError(
        ErrorCode.INVALID_ARGUMENT,
        f"Unknown capture target syntax: {s!r}",
        details={"target": s},
    )


class Capturer:
    """Selects and falls back across capture backends according to §7 strategy."""

    def __init__(self, backends: dict[str, CaptureBackend], cfg: Config) -> None:
        self._backends = dict(backends)
        self._cfg = cfg

    def _require_backend(self, name: str) -> CaptureBackend:
        backend = self._backends.get(name)
        if backend is None:
            raise EdmError(
                ErrorCode.CAPTURE_FAILED,
                f"Required capture backend {name!r} is not configured.",
                details={"backend": name},
            )
        ok, reason = backend.available()
        if not ok:
            raise EdmError(
                ErrorCode.CAPTURE_FAILED,
                f"Capture backend {name!r} is unavailable: {reason}",
                details={"backend": name, "reason": reason},
            )
        return backend

    def capture(
        self,
        target: CaptureTarget,
        restore: bool = False,
    ) -> tuple[Frame, WindowInfo | None]:
        """Capture *target* and return ``(Frame, WindowInfo | None)``."""
        if target.kind == "screen":
            gdi = self._require_backend("gdi")
            return gdi.capture_rect(virtual_screen()), None

        if target.kind == "monitor":
            assert target.monitor is not None
            monitors = list_monitors()
            matched = [m for m in monitors if m.index == target.monitor]
            if not matched:
                raise EdmError(
                    ErrorCode.INVALID_ARGUMENT,
                    f"Monitor index {target.monitor} not found.",
                    details={"monitor": target.monitor, "count": len(monitors)},
                )
            gdi = self._require_backend("gdi")
            return gdi.capture_rect(matched[0].rect), None

        if target.kind == "region":
            assert target.rect is not None
            gdi = self._require_backend("gdi")
            return gdi.capture_rect(target.rect), None

        # target.kind == "window"
        assert target.query is not None
        win, _alts = resolve_window(target.query)
        if win.minimized:
            if not restore:
                raise EdmError(
                    ErrorCode.WINDOW_MINIMIZED,
                    f"Window {win.hwnd} ({win.title!r}) is minimized.",
                    details={"hwnd": win.hwnd, "title": win.title},
                )
            _restore_window(win.hwnd)
            win = window_info(win.hwnd)

        vis = visible_fraction(win.rect, {win.hwnd}, root_window_at)
        order = (
            ["gdi", "wgc", "printwindow"] if vis >= _OCCLUSION_THRESHOLD else ["wgc", "printwindow"]
        )

        attempts: list[dict[str, object]] = []
        for name in order:
            backend = self._backends.get(name)
            if backend is None:
                attempts.append({"backend": name, "ok": False, "reason": "not configured"})
                continue
            avail, reason = backend.available()
            if not avail:
                attempts.append({"backend": name, "ok": False, "reason": reason})
                continue
            try:
                frame = backend.capture_window(win.hwnd)
            except EdmError as exc:
                attempts.append({"backend": name, "ok": False, "reason": exc.message})
                continue

            if is_blank(frame.image):
                attempts.append({"backend": name, "ok": False, "reason": "blank"})
                continue

            attempts.append({"backend": name, "ok": True, "reason": "ok"})
            return (
                Frame(
                    image=frame.image,
                    screen_rect=frame.screen_rect,
                    backend=frame.backend,
                    captured_at=frame.captured_at,
                    attempts=attempts,
                ),
                win,
            )

        raise EdmError(
            ErrorCode.CAPTURE_BLANK,
            f"All capture backends failed or returned blank for hwnd={win.hwnd}.",
            details={"hwnd": win.hwnd, "attempts": attempts},
        )
