"""Deterministic fake backends for testing and isolated environments."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from PIL import Image

from edm.geometry import Point, Rect
from edm.win32.session import SessionInfo, SessionState


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

    name: str = "fake"
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

    def capture_rect(self, rect: Rect) -> Image.Image:
        """Crop the deterministic image to *rect*."""
        return self.full_image().crop((rect.left, rect.top, rect.right, rect.bottom))


@dataclass
class FakeInputSink:
    """In-memory input event sink for unit tests."""

    events: list[dict[str, Any]] = field(default_factory=list)
    cursor_pos: Point = field(default_factory=lambda: Point(500, 500))
