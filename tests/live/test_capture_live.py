"""Live GDI capture acceptance tests (L1)."""

from __future__ import annotations

import ctypes
import subprocess
from ctypes import wintypes
from pathlib import Path

import pytest

from edm.capture.gdi import GdiBackend
from edm.geometry import Rect
from edm.win32.api import user32
from edm.win32.windows import WindowInfo

_ClientToScreen = user32.ClientToScreen
_ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
_ClientToScreen.restype = wintypes.BOOL


def _client_origin(hwnd: int) -> tuple[int, int]:
    pt = wintypes.POINT(0, 0)
    _ClientToScreen(hwnd, ctypes.byref(pt))
    return int(pt.x), int(pt.y)


@pytest.mark.live
def test_gdi_pixel_colors(
    target_app: tuple[WindowInfo, Path, subprocess.Popen[str]],
) -> None:
    """L1: Verify GDI captures exact red, green, and blue square center pixels."""
    win, _log_path, _proc = target_app
    ox, oy = _client_origin(win.hwnd)
    frame = GdiBackend().capture_rect(Rect(ox, oy, ox + 400, oy + 160))

    assert frame.image.getpixel((80, 80)) == (255, 0, 0)
    assert frame.image.getpixel((200, 80)) == (0, 255, 0)
    assert frame.image.getpixel((320, 80)) == (0, 0, 255)
