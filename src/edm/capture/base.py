"""Base capture protocol, frame container, and blank-frame detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from PIL import Image, ImageStat

from edm.geometry import Rect


@dataclass(frozen=True)
class Frame:
    """Captured RGB image along with screen bounds and backend metadata."""

    image: Image.Image
    screen_rect: Rect
    backend: str
    captured_at: float
    attempts: list[dict[str, Any]]


class CaptureBackend(Protocol):
    """Protocol implemented by all screen/window capture backends."""

    name: str

    def available(self) -> tuple[bool, str]:
        """Return whether the backend is available and a human-readable reason."""
        ...

    def capture_rect(self, rect: Rect) -> Frame:
        """Capture the screen region *rect* in physical screen pixels."""
        ...

    def capture_window(self, hwnd: int) -> Frame:
        """Capture the window identified by *hwnd*."""
        ...


def is_blank(img: Image.Image) -> bool:
    """Return True if *img* looks uniform/blank according to design thresholds."""
    rgb = img.convert("RGB")
    stat = ImageStat.Stat(rgb)
    stddevs = stat.stddev
    extrema = stat.extrema
    return all(sd < 2.0 and (hi - lo) < 8 for sd, (lo, hi) in zip(stddevs, extrema, strict=True))
