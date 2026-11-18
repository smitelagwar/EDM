"""GDI screen/window capture backend using ``mss`` and cursor query."""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

import mss
from PIL import Image

from edm.capture.base import Frame
from edm.errors import EdmError, ErrorCode
from edm.geometry import Point, Rect
from edm.win32.api import user32
from edm.win32.windows import window_info

_CURSOR_SHOWING = 0x00000001


class _CURSORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hCursor", wintypes.HANDLE),
        ("ptScreenPos", wintypes.POINT),
    ]


_GetCursorInfo = user32.GetCursorInfo
_GetCursorInfo.argtypes = [ctypes.POINTER(_CURSORINFO)]
_GetCursorInfo.restype = wintypes.BOOL


def cursor_position() -> Point | None:
    """Return the current visible cursor position in screen coordinates, or None."""
    ci = _CURSORINFO()
    ci.cbSize = ctypes.sizeof(_CURSORINFO)
    if not _GetCursorInfo(ctypes.byref(ci)):
        return None
    if (ci.flags & _CURSOR_SHOWING) == 0:
        return None
    return Point(int(ci.ptScreenPos.x), int(ci.ptScreenPos.y))


class GdiBackend:
    """Capture backend backed by ``mss`` (BitBlt / GDI)."""

    name: str = "gdi"

    def available(self) -> tuple[bool, str]:
        """Report GDI backend availability."""
        return True, "mss"

    def capture_rect(self, rect: Rect) -> Frame:
        """Capture *rect* from the virtual screen via ``mss``."""
        if rect.width <= 0 or rect.height <= 0:
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"Capture rect must have positive dimensions, got {rect}",
                details={"rect": rect.as_list()},
            )
        monitor = {
            "left": rect.left,
            "top": rect.top,
            "width": rect.width,
            "height": rect.height,
        }
        try:
            with mss.mss() as sct:
                shot = sct.grab(monitor)
                img = Image.frombytes("RGB", shot.size, shot.rgb)
        except Exception as exc:
            raise EdmError(
                ErrorCode.CAPTURE_FAILED,
                f"GDI capture_rect failed: {exc}",
                details={"rect": rect.as_list()},
            ) from exc

        if img.size != (rect.width, rect.height):
            raise EdmError(
                ErrorCode.CAPTURE_FAILED,
                f"GDI capture size mismatch: expected {(rect.width, rect.height)}, got {img.size}",
                details={"expected": [rect.width, rect.height], "actual": list(img.size)},
            )

        return Frame(
            image=img,
            screen_rect=rect,
            backend=self.name,
            captured_at=time.time(),
            attempts=[{"backend": self.name, "ok": True}],
        )

    def capture_window(self, hwnd: int) -> Frame:
        """Capture the extended frame bounds of *hwnd* via GDI."""
        info = window_info(hwnd)
        if info.minimized:
            raise EdmError(
                ErrorCode.WINDOW_MINIMIZED,
                f"Window {hwnd} is minimized and cannot be captured.",
                details={"hwnd": hwnd},
            )
        if info.rect.width <= 0 or info.rect.height <= 0:
            raise EdmError(
                ErrorCode.CAPTURE_FAILED,
                f"Window {hwnd} has empty bounds: {info.rect}",
                details={"hwnd": hwnd, "rect": info.rect.as_list()},
            )
        return self.capture_rect(info.rect)
