"""Core EDM service facade."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from edm.capture.base import CaptureBackend, Frame
from edm.capture.gdi import GdiBackend, cursor_position
from edm.capture.printwindow import PrintWindowBackend
from edm.capture.select import Capturer, CaptureTarget, parse_target
from edm.capture.wgc import WgcBackend
from edm.config import Config, load_config
from edm.doctor import run_doctor
from edm.errors import EdmError, ErrorCode
from edm.fakes import (
    FakeCaptureBackend,
    FakeInputSink,
    FakeSession,
    fake_cursor_position,
    fake_monitors,
    fake_virtual_screen,
    fake_windows,
)
from edm.geometry import CoordSpace, ImageMapping, Point, Rect
from edm.observe.render import draw_cursor, draw_grid, encode_image, make_preview, zoom_crop
from edm.observe.store import ObservationStore
from edm.win32.dpi import ensure_dpi_awareness
from edm.win32.monitors import MonitorInfo, list_monitors, virtual_screen
from edm.win32.session import SessionInfo, get_session
from edm.win32.windows import (
    WindowInfo,
    _matches_query,
    list_windows,
    parse_window_query,
    select_window,
)


@dataclass(frozen=True)
class Result:
    """Unified return envelope for EDM service operations."""

    payload: dict[str, Any]
    image: bytes | None = None
    mime: str | None = None


def _window_to_dict(win: WindowInfo) -> dict[str, Any]:
    return {
        "hwnd": win.hwnd,
        "title": win.title,
        "class_name": win.class_name,
        "pid": win.pid,
        "exe": win.exe,
        "rect": win.rect.as_list(),
        "minimized": win.minimized,
        "maximized": win.maximized,
        "visible": win.visible,
        "cloaked": win.cloaked,
        "topmost": win.topmost,
        "foreground": win.foreground,
        "monitor_index": win.monitor_index,
        "integrity": str(win.integrity),
        "z_order": win.z_order,
    }


def _monitor_to_dict(mon: MonitorInfo) -> dict[str, Any]:
    return {
        "index": mon.index,
        "device": mon.device,
        "rect": mon.rect.as_list(),
        "work_rect": mon.work_rect.as_list(),
        "dpi": mon.dpi,
        "scale": mon.scale,
        "primary": mon.primary,
    }


class Edm:
    """Facade coordinating session, capture, perception, and input backends."""

    def __init__(
        self,
        cfg: Config | None = None,
        *,
        session_provider: Callable[[], SessionInfo] = get_session,
        capture_backends: dict[str, CaptureBackend] | None = None,
        input_sink: Any = None,
        clock: Callable[[], float] = time.time,
        monitors_provider: Callable[[], list[MonitorInfo]] = list_monitors,
        virtual_screen_provider: Callable[[], Rect] = virtual_screen,
        windows_provider: Callable[[], list[WindowInfo]] = list_windows,
        cursor_provider: Callable[[], Point | None] = cursor_position,
        store: ObservationStore | None = None,
    ) -> None:
        self.dpi_awareness = ensure_dpi_awareness()
        self.cfg = cfg if cfg is not None else load_config()
        self.session_provider = session_provider
        self.clock = clock
        self._monitors_provider = monitors_provider
        self._virtual_screen_provider = virtual_screen_provider
        self._windows_provider = windows_provider
        self._cursor_provider = cursor_provider

        if capture_backends is not None:
            self.capture_backends: dict[str, CaptureBackend] = dict(capture_backends)
        else:
            self.capture_backends = {
                "gdi": GdiBackend(),
                "wgc": WgcBackend(self.cfg),
                "printwindow": PrintWindowBackend(),
            }
        self.input_sink = input_sink
        self.store = (
            store
            if store is not None
            else ObservationStore(self.cfg.data_dir / "observations", self.cfg, clock=self.clock)
        )
        self.capturer = Capturer(
            self.capture_backends,
            self.cfg,
            virtual_screen_provider=self._virtual_screen_provider,
            monitors_provider=self._monitors_provider,
            window_resolver=self._resolve_window,
            window_info_provider=self._window_info,
            hit_test_provider=self._hit_test,
        )

    def _resolve_window(self, query: str) -> tuple[WindowInfo, list[WindowInfo]]:
        wq = parse_window_query(query)
        return select_window(self._windows_provider(), wq)

    def _window_info(self, hwnd: int) -> WindowInfo:
        for win in self._windows_provider():
            if win.hwnd == hwnd:
                return win
        raise EdmError(
            ErrorCode.WINDOW_NOT_FOUND,
            f"Window not found: hwnd={hwnd}",
            details={"hwnd": hwnd},
        )

    def _hit_test(self, p: Point) -> int:
        for win in sorted(self._windows_provider(), key=lambda w: w.z_order):
            if win.visible and not win.minimized and win.rect.contains(p):
                return win.hwnd
        return 0

    @classmethod
    def build_default(cls, cfg: Config | None = None) -> Edm:
        """Build an ``Edm`` instance, using fake backends when ``EDM_FAKE=1``."""
        if os.environ.get("EDM_FAKE") == "1":
            return cls(
                cfg,
                session_provider=FakeSession(),
                capture_backends={"gdi": FakeCaptureBackend()},
                input_sink=FakeInputSink(),
                monitors_provider=fake_monitors,
                virtual_screen_provider=fake_virtual_screen,
                windows_provider=fake_windows,
                cursor_provider=fake_cursor_position,
            )
        return cls(cfg)

    def doctor(self) -> Result:
        """Run environment diagnostics and return a ``Result``."""
        return Result(payload=run_doctor(self))

    def list_monitors(self) -> Result:
        """Return all display monitors."""
        mons = [_monitor_to_dict(m) for m in self._monitors_provider()]
        return Result(
            payload={
                "ok": True,
                "action": "list_monitors",
                "monitors": mons,
                "details": {},
                "warnings": [],
            }
        )

    def list_windows(
        self,
        query: str | None = None,
        include_minimized: bool = True,
    ) -> Result:
        """List top-level windows, optionally filtered by *query*."""
        cands = self._windows_provider()
        if not include_minimized:
            cands = [w for w in cands if not w.minimized]
        if query is not None:
            wq = parse_window_query(query)
            cands = [w for w in cands if _matches_query(w, wq)]
        ordered = sorted(cands, key=lambda w: w.z_order)
        return Result(
            payload={
                "ok": True,
                "action": "list_windows",
                "windows": [_window_to_dict(w) for w in ordered],
                "details": {},
                "warnings": [],
            }
        )

    def _foreground_summary(self) -> dict[str, Any] | None:
        for win in self._windows_provider():
            if win.foreground:
                return {"hwnd": win.hwnd, "title": win.title, "exe": win.exe}
        return None

    def screenshot(
        self,
        target: str = "screen",
        max_edge: int | None = None,
        grid: bool = False,
        cursor: bool = True,
        marks: bool = False,
        restore: bool = False,
    ) -> Result:
        """Capture *target*, persist observation, and return preview image bytes."""
        del marks
        parsed = parse_target(target)
        frame, win = self.capturer.capture(parsed, restore=restore)
        edge = max_edge if max_edge is not None else self.cfg.preview_max_edge
        preview = make_preview(frame.image, edge)
        mapping = ImageMapping(
            frame_rect=frame.screen_rect,
            crop=Rect(0, 0, frame.image.width, frame.image.height),
            image_size=preview.size,
        )
        if cursor:
            pos = self._cursor_provider()
            if pos is not None and frame.screen_rect.contains(pos):
                preview = draw_cursor(preview, mapping.from_screen(pos))
        if grid:
            preview = draw_grid(preview)

        win_dict = _window_to_dict(win) if win is not None else None
        obs = self.store.add(
            frame,
            preview,
            mapping,
            target=target,
            window=win_dict,
        )
        img_bytes, mime = encode_image(preview, self.cfg.max_image_bytes)
        return Result(
            payload={
                "ok": True,
                "action": "screenshot",
                "observation": obs.to_public(),
                "details": {
                    "foreground_window": self._foreground_summary(),
                    "attempts": frame.attempts,
                },
                "warnings": [],
            },
            image=img_bytes,
            mime=mime,
        )

    def zoom(
        self,
        observation_id: str,
        x: float,
        y: float,
        w: float,
        h: float,
        coord_space: CoordSpace = "pixel",
        fresh: bool = False,
        factor: float | None = None,
    ) -> Result:
        """Zoom into a sub-region of an existing observation."""
        parent = self.store.get(observation_id)
        if w <= 0 or h <= 0:
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"Zoom width and height must be positive, got {(w, h)}.",
                details={"w": w, "h": h},
            )

        pw, ph = parent.mapping.image_size
        if coord_space == "norm1000":
            if x < 0 or y < 0 or x + w > 1000 or y + h > 1000:
                raise EdmError(
                    ErrorCode.POINT_OUT_OF_BOUNDS,
                    f"Normalized zoom box ({x}, {y}, {w}, {h}) exceeds [0, 1000].",
                )
            px_x = round(x / 1000.0 * pw)
            px_y = round(y / 1000.0 * ph)
            px_w = max(1, round(w / 1000.0 * pw))
            px_h = max(1, round(h / 1000.0 * ph))
        elif coord_space == "pixel":
            px_x, px_y, px_w, px_h = round(x), round(y), round(w), round(h)
            if px_x < 0 or px_y < 0 or px_x + px_w > pw or px_y + px_h > ph:
                raise EdmError(
                    ErrorCode.POINT_OUT_OF_BOUNDS,
                    f"Zoom box ({px_x}, {px_y}, {px_w}, {px_h}) exceeds image bounds {pw}x{ph}.",
                )
        else:
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"Unsupported coord_space: {coord_space!r}",
            )

        crop_in_image = Rect.from_xywh(px_x, px_y, px_w, px_h)
        orig_crop = parent.mapping.child(crop_in_image, (1, 1)).crop

        if fresh:
            screen_crop = Rect(
                parent.frame_rect.left + orig_crop.left,
                parent.frame_rect.top + orig_crop.top,
                parent.frame_rect.left + orig_crop.right,
                parent.frame_rect.top + orig_crop.bottom,
            )
            frame, _ = self.capturer.capture(CaptureTarget(kind="region", rect=screen_crop))
            zoomed = zoom_crop(
                frame.image,
                Rect(0, 0, frame.image.width, frame.image.height),
                self.cfg.preview_max_edge,
                factor,
            )
            mapping = ImageMapping(
                frame_rect=frame.screen_rect,
                crop=Rect(0, 0, frame.image.width, frame.image.height),
                image_size=zoomed.size,
            )
            target_str = (
                f"region:{screen_crop.left},{screen_crop.top},"
                f"{screen_crop.width},{screen_crop.height}"
            )
        else:
            orig = self.store.load_original(parent)
            zoomed = zoom_crop(orig, orig_crop, self.cfg.preview_max_edge, factor)
            mapping = parent.mapping.child(crop_in_image, zoomed.size)
            frame = Frame(
                image=orig,
                screen_rect=parent.frame_rect,
                backend=parent.backend,
                captured_at=self.clock(),
                attempts=[],
            )
            target_str = parent.target

        obs = self.store.add(
            frame,
            zoomed,
            mapping,
            target=target_str,
            window=parent.window,
            parent_id=parent.id,
        )
        img_bytes, mime = encode_image(zoomed, self.cfg.max_image_bytes)
        return Result(
            payload={
                "ok": True,
                "action": "zoom",
                "observation": obs.to_public(),
                "details": {"fresh": fresh},
                "warnings": [],
            },
            image=img_bytes,
            mime=mime,
        )
