"""Screen and window capture backends."""

from edm.capture.base import CaptureBackend, Frame, is_blank
from edm.capture.gdi import GdiBackend, cursor_position

__all__ = ["CaptureBackend", "Frame", "GdiBackend", "cursor_position", "is_blank"]
