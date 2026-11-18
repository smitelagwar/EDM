from __future__ import annotations

import ctypes
import sys
import types
from typing import Any

import numpy as np
import pytest

import edm.capture.printwindow as pw_mod
import edm.capture.wgc as wgc_mod
from edm.config import Config
from edm.geometry import Rect
from edm.win32.process import Integrity
from edm.win32.windows import WindowInfo


def _make_win(rect: Rect) -> WindowInfo:
    return WindowInfo(
        hwnd=101,
        title="Mock",
        class_name="MockClass",
        pid=123,
        exe="mock.exe",
        rect=rect,
        minimized=False,
        maximized=False,
        visible=True,
        cloaked=False,
        topmost=False,
        foreground=True,
        monitor_index=0,
        integrity=Integrity.medium,
        z_order=0,
    )


def test_wgc_falls_back_to_draw_border_none_on_start_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_draw_border: list[bool | None] = []
    win = _make_win(Rect(0, 0, 100, 80))
    monkeypatch.setattr(wgc_mod, "window_info", lambda _hwnd: win)

    class _FakeFrame:
        def __init__(self) -> None:
            # BGRA 80x100 with red pixel (B=0, G=0, R=255, A=255)
            arr = np.zeros((80, 100, 4), dtype=np.uint8)
            arr[:, :, 2] = 255
            arr[:, :, 3] = 255
            self.frame_buffer = arr

    class _FakeControl:
        def stop(self) -> None:
            pass

    class _FakeWindowsCapture:
        def __init__(self, **kwargs: Any) -> None:
            self._draw_border = kwargs.get("draw_border")
            seen_draw_border.append(self._draw_border)
            self._handlers: list[Any] = []

        def event(self, fn: Any) -> None:
            self._handlers.append(fn)

        def start_free_threaded(self) -> _FakeControl:
            if self._draw_border is False:
                raise RuntimeError("Toggling capture border is not supported")
            ctrl = _FakeControl()
            self._handlers[0](_FakeFrame(), ctrl)
            return ctrl

    fake_mod = types.ModuleType("windows_capture")
    fake_mod.WindowsCapture = _FakeWindowsCapture  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "windows_capture", fake_mod)

    frame = wgc_mod.WgcBackend(Config()).capture_window(101)
    assert seen_draw_border == [False, None]
    assert frame.backend == "wgc"
    assert frame.image.size == (100, 80)
    assert frame.image.getpixel((10, 10)) == (255, 0, 0)


def test_printwindow_crops_dwm_offset(monkeypatch: pytest.MonkeyPatch) -> None:
    dwm_rect = Rect(107, 100, 509, 332)  # 402x232
    win_rect = Rect(100, 100, 516, 339)  # 416x239 (7px shadow on left/right/bottom)
    monkeypatch.setattr(pw_mod, "window_info", lambda _hwnd: _make_win(dwm_rect))
    monkeypatch.setattr(pw_mod, "_get_window_rect", lambda _hwnd, _fb: win_rect)
    monkeypatch.setattr(pw_mod, "_GetDC", lambda _hwnd: 1)
    monkeypatch.setattr(pw_mod, "_ReleaseDC", lambda _hwnd, _hdc: 1)
    monkeypatch.setattr(pw_mod, "_CreateCompatibleDC", lambda _hdc: 2)
    monkeypatch.setattr(pw_mod, "_DeleteDC", lambda _hdc: 1)
    monkeypatch.setattr(pw_mod, "_CreateCompatibleBitmap", lambda _hdc, _w, _h: 3)
    monkeypatch.setattr(pw_mod, "_SelectObject", lambda _hdc, _obj: 4)
    monkeypatch.setattr(pw_mod, "_DeleteObject", lambda _obj: 1)
    monkeypatch.setattr(pw_mod, "_PrintWindow", lambda _hwnd, _hdc, _flags: 1)

    def _fake_get_dibits(
        _hdc: Any,
        _hbm: Any,
        _start: int,
        lines: int,
        buf_ptr: Any,
        _bmi: Any,
        _usage: int,
    ) -> int:
        # Fill pixel (x=7, y=0) in 416x239 BGRA buffer with red (B=0, G=0, R=255, X=255)
        raw = ctypes.cast(buf_ptr, ctypes.POINTER(ctypes.c_ubyte * (416 * 239 * 4))).contents
        idx = (0 * 416 + 7) * 4
        raw[idx + 0] = 0
        raw[idx + 1] = 0
        raw[idx + 2] = 255
        raw[idx + 3] = 255
        return lines

    monkeypatch.setattr(pw_mod, "_GetDIBits", _fake_get_dibits)

    frame = pw_mod.PrintWindowBackend().capture_window(101)
    assert frame.screen_rect == dwm_rect
    assert frame.image.size == (402, 232)
    assert frame.image.getpixel((0, 0)) == (255, 0, 0)
