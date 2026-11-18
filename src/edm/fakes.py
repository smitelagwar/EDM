"""Deterministic fake backends for testing and isolated environments."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from PIL import Image

from edm.capture.base import Frame
from edm.errors import EdmError, ErrorCode
from edm.geometry import Point, Rect
from edm.win32.monitors import MonitorInfo
from edm.win32.process import Integrity
from edm.win32.session import SessionInfo, SessionState
from edm.win32.windows import WindowInfo


def fake_monitors() -> list[MonitorInfo]:
    """Return a deterministic single-monitor list."""
    return [
        MonitorInfo(
            index=0,
            device=r"\\.\DISPLAY1",
            rect=Rect(0, 0, 2560, 1440),
            work_rect=Rect(0, 0, 2560, 1400),
            dpi=96,
            scale=1.0,
            primary=True,
        )
    ]


def fake_virtual_screen() -> Rect:
    """Return the deterministic fake virtual screen rectangle."""
    return Rect(0, 0, 2560, 1440)


def fake_windows() -> list[WindowInfo]:
    """Return a deterministic list of fake top-level windows."""
    return [
        WindowInfo(
            hwnd=1001,
            title="EDM Fake Window",
            class_name="FakeWindowClass",
            pid=4242,
            exe="fake.exe",
            rect=Rect(100, 100, 900, 700),
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
    ]


def fake_cursor_position() -> Point | None:
    """Return a deterministic fake cursor position away from (0, 0)."""
    return Point(500, 500)


@dataclass
class FakeSession:
    """Fake session provider returning a configurable ``SessionInfo``."""

    state: SessionState = "ok"

    def __call__(self) -> SessionInfo:
        if self.state == "isolated_desktop":
            return SessionInfo(
                station="WinSta0",
                thread_desktop="exebox-fake",
                input_desktop="Default",
                state="isolated_desktop",
            )
        if self.state == "secure_desktop":
            return SessionInfo(
                station="WinSta0",
                thread_desktop="Default",
                input_desktop="Winlogon",
                state="secure_desktop",
            )
        if self.state == "session_locked":
            return SessionInfo(
                station="WinSta0",
                thread_desktop="Default",
                input_desktop="Default",
                state="session_locked",
            )
        return SessionInfo(
            station="WinSta0",
            thread_desktop="Default",
            input_desktop="Default",
            state="ok",
        )


@dataclass
class FakeCaptureBackend:
    """Deterministic 2560x1440 fake capture backend with RGB test squares."""

    name: str = "gdi"
    width: int = 2560
    height: int = 1440

    def available(self) -> tuple[bool, str]:
        """Report fake capture backend availability."""
        return True, "fake"

    def full_image(self) -> Image.Image:
        """Render the deterministic 2560x1440 RGB image."""
        img = Image.new("RGB", (self.width, self.height), (32, 32, 32))
        img.paste((255, 0, 0), (200, 200, 300, 300))
        img.paste((0, 255, 0), (400, 200, 500, 300))
        img.paste((0, 0, 255), (600, 200, 700, 300))
        return img

    def capture_rect(self, rect: Rect) -> Frame:
        """Crop the deterministic image to *rect* and return a ``Frame``."""
        cropped = self.full_image().crop((rect.left, rect.top, rect.right, rect.bottom))
        return Frame(
            image=cropped,
            screen_rect=rect,
            backend=self.name,
            captured_at=time.time(),
            attempts=[{"backend": self.name, "ok": True}],
        )

    def capture_window(self, hwnd: int) -> Frame:
        """Capture a fake window matching *hwnd*."""
        for win in fake_windows():
            if win.hwnd == hwnd:
                return self.capture_rect(win.rect)
        raise EdmError(
            ErrorCode.WINDOW_NOT_FOUND,
            f"Fake window not found: hwnd={hwnd}",
            details={"hwnd": hwnd},
        )


@dataclass
class FakeInputSink:
    """In-memory input event sink for unit tests."""

    events: list[dict[str, Any]] = field(default_factory=list)
    cursor_pos: Point = field(default_factory=lambda: Point(500, 500))
