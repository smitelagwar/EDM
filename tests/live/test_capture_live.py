"""Live GDI, WGC, and PrintWindow capture acceptance tests (L1-L3)."""

from __future__ import annotations

import ctypes
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

import pytest

from edm.capture.gdi import GdiBackend
from edm.capture.printwindow import PrintWindowBackend
from edm.capture.select import Capturer, CaptureTarget
from edm.capture.wgc import WgcBackend
from edm.config import Config
from edm.errors import EdmError
from edm.geometry import Rect
from edm.win32.api import user32
from edm.win32.windows import WindowInfo, resolve_window

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


@pytest.mark.live
def test_window_capture_size(
    target_app: tuple[WindowInfo, Path, subprocess.Popen[str]],
) -> None:
    """L2: Verify window capture dimensions match DWM extended frame bounds."""
    win, _log_path, _proc = target_app
    cfg = Config()
    capturer = Capturer(
        {
            "gdi": GdiBackend(),
            "wgc": WgcBackend(cfg),
            "printwindow": PrintWindowBackend(),
        },
        cfg,
    )
    frame, captured_win = capturer.capture(CaptureTarget(kind="window", query=f"hwnd:{win.hwnd}"))
    assert captured_win is not None
    assert frame.image.size == (win.rect.width, win.rect.height)


@pytest.mark.live
def test_occluded_window_uses_wgc_or_printwindow(
    target_app: tuple[WindowInfo, Path, subprocess.Popen[str]],
) -> None:
    """L3: Verify occluded window falls back to WGC or PrintWindow with intact pixels."""
    win, _log_path, _proc = target_app
    ox, oy = _client_origin(win.hwnd)
    dx = ox - win.rect.left
    dy = oy - win.rect.top

    occluder_code = (
        "import tkinter as tk; "
        "r = tk.Tk(); r.title('EDM Occluder'); r.attributes('-topmost', True); "
        f"r.geometry('600x400+{win.rect.left + 50}+{win.rect.top + 20}'); r.mainloop()"
    )
    occ = subprocess.Popen([sys.executable, "-c", occluder_code])
    try:
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            try:
                resolve_window("title:EDM Occluder")
                break
            except EdmError:
                time.sleep(0.1)

        cfg = Config()
        capturer = Capturer(
            {
                "gdi": GdiBackend(),
                "wgc": WgcBackend(cfg),
                "printwindow": PrintWindowBackend(),
            },
            cfg,
        )
        frame, _ = capturer.capture(CaptureTarget(kind="window", query=f"hwnd:{win.hwnd}"))
        assert frame.backend != "gdi"
        assert frame.backend in {"wgc", "printwindow"}
        assert frame.image.getpixel((dx + 80, dy + 80)) == (255, 0, 0)
    finally:
        occ.kill()
        occ.wait(timeout=5)
