"""Windows Graphics Capture (WGC) backend using ``windows-capture``."""

from __future__ import annotations

import contextlib
import threading
import time
from typing import Any

from PIL import Image

from edm.capture.base import Frame
from edm.config import Config
from edm.errors import EdmError, ErrorCode
from edm.geometry import Rect
from edm.win32.windows import window_info


class WgcBackend:
    """Capture backend backed by Windows Graphics Capture (``windows-capture``)."""

    name: str = "wgc"

    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg

    def available(self) -> tuple[bool, str]:
        """Report whether ``windows-capture`` can be imported."""
        try:
            import windows_capture  # noqa: F401
        except Exception as exc:
            return False, str(exc)
        return True, "windows-capture"

    def capture_rect(self, rect: Rect) -> Frame:
        """WGC targets windows rather than arbitrary screen rectangles."""
        raise EdmError(
            ErrorCode.CAPTURE_FAILED,
            "WgcBackend only supports capture_window.",
            details={"backend": self.name, "rect": rect.as_list()},
        )

    def _create_capture(self, cls: Any, hwnd: int) -> Any:
        try:
            return cls(cursor_capture=False, draw_border=False, window_hwnd=hwnd)
        except Exception:
            return cls(cursor_capture=False, draw_border=None, window_hwnd=hwnd)

    def capture_window(self, hwnd: int) -> Frame:
        """Capture a single frame of *hwnd* via WGC within ``cfg.wgc_timeout_s``."""
        info = window_info(hwnd)
        if info.minimized:
            raise EdmError(
                ErrorCode.WINDOW_MINIMIZED,
                f"Window {hwnd} is minimized and cannot be captured.",
                details={"backend": self.name, "hwnd": hwnd},
            )

        try:
            from windows_capture import WindowsCapture
        except Exception as exc:
            raise EdmError(
                ErrorCode.DEPENDENCY_MISSING,
                f"windows-capture is not available: {exc}",
                details={"backend": self.name},
            ) from exc

        done = threading.Event()
        captured: list[Image.Image] = []
        errors: list[str] = []

        capture = self._create_capture(WindowsCapture, hwnd)

        def on_frame_arrived(frame: Any, capture_control: Any) -> None:
            try:
                buf = frame.frame_buffer
                rgb = buf[:, :, [2, 1, 0]]
                captured.append(Image.fromarray(rgb, "RGB"))
            except Exception as exc:
                errors.append(str(exc))
            finally:
                with contextlib.suppress(Exception):
                    capture_control.stop()
                done.set()

        def on_closed() -> None:
            done.set()

        capture.event(on_frame_arrived)
        capture.event(on_closed)

        try:
            ctrl = capture.start_free_threaded()
        except Exception as exc:
            raise EdmError(
                ErrorCode.CAPTURE_FAILED,
                f"WGC failed to start capture for hwnd={hwnd}: {exc}",
                details={"backend": self.name, "hwnd": hwnd},
            ) from exc

        finished = done.wait(timeout=self._cfg.wgc_timeout_s)
        if not finished:
            with contextlib.suppress(Exception):
                ctrl.stop()
            raise EdmError(
                ErrorCode.CAPTURE_FAILED,
                f"WGC capture timed out after {self._cfg.wgc_timeout_s}s",
                details={"backend": self.name, "hwnd": hwnd},
            )

        if errors or not captured:
            reason = "; ".join(errors) if errors else "no frame received"
            raise EdmError(
                ErrorCode.CAPTURE_FAILED,
                f"WGC capture failed: {reason}",
                details={"backend": self.name, "hwnd": hwnd},
            )

        return Frame(
            image=captured[0],
            screen_rect=info.rect,
            backend=self.name,
            captured_at=time.time(),
            attempts=[{"backend": self.name, "ok": True}],
        )
