"""Core EDM service facade."""

from __future__ import annotations

import json
import math
import os
import re
import time
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from PIL import Image

from edm.actions import clipboard as win32_clipboard
from edm.actions.addressing import Address, resolve_point
from edm.actions.guard import Guard
from edm.actions.keys import (
    chord_events,
    key_state_events,
    parse_chord,
    unicode_events,
)
from edm.actions.killswitch import KillSwitch
from edm.actions.launch import LaunchSpec, resolve_launch_target, shell_execute
from edm.actions.mouse import (
    click_events,
    interpolate_path,
    mouse_button_events,
    wheel_events,
)
from edm.actions.sequence import Step, execute_sequence
from edm.actions.waits import check_stale, wait_for_stable, wait_until
from edm.actions.windowops import WindowActionName
from edm.actions.windowops import window_action as win32_window_action
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
    FakeClipboard,
    FakeInputSink,
    FakeOcrEngine,
    FakeSession,
    FakeSnipSelector,
    FakeUiaProvider,
    fake_cursor_position,
    fake_monitors,
    fake_virtual_screen,
    fake_windows,
)
from edm.geometry import CoordSpace, ImageMapping, Point, Rect
from edm.observe.diff import patch_diff
from edm.observe.render import (
    draw_cursor,
    draw_grid,
    draw_marks,
    encode_image,
    make_preview,
    zoom_crop,
)
from edm.observe.store import Mark, Observation, ObservationStore
from edm.perception.ocr import MatchMode, OcrLine, match_text, ocr_image
from edm.perception.uia import Element, ElementProvider, collect_elements
from edm.snip.overlay import run_snip
from edm.win32.api import user32
from edm.win32.dpi import ensure_dpi_awareness
from edm.win32.input import InputSink, Win32InputSink
from edm.win32.monitors import MonitorInfo, list_monitors, virtual_screen
from edm.win32.process import Integrity, integrity_rank, self_integrity
from edm.win32.session import SessionInfo, get_session
from edm.win32.windows import (
    WindowInfo,
    _matches_query,
    list_windows,
    parse_window_query,
    root_window_at,
    select_window,
)

_GetLastActivePopup = user32.GetLastActivePopup
_GetLastActivePopup.argtypes = [wintypes.HWND]
_GetLastActivePopup.restype = wintypes.HWND


def _win32_last_active_popup(hwnd: int) -> int:
    return int(_GetLastActivePopup(hwnd) or 0)


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


def _marks_in_image(marks: list[Mark], mapping: ImageMapping) -> list[tuple[int, Rect]]:
    out: list[tuple[int, Rect]] = []
    for m in marks:
        x1, y1 = mapping.from_screen(Point(m.rect.left, m.rect.top))
        x2, y2 = mapping.from_screen(Point(m.rect.right, m.rect.bottom))
        out.append((m.id, Rect(round(x1), round(y1), round(x2), round(y2))))
    return out


def _element_to_dict(el: Element) -> dict[str, Any]:
    return {
        "mark": el.mark,
        "name": el.name,
        "control_type": el.control_type,
        "rect": el.rect.as_list(),
        "enabled": el.enabled,
        "automation_id": el.automation_id,
        "value": el.value,
    }


class Edm:
    """Facade coordinating session, capture, perception, and input backends."""

    def __init__(
        self,
        cfg: Config | None = None,
        *,
        session_provider: Callable[[], SessionInfo] = get_session,
        capture_backends: dict[str, CaptureBackend] | None = None,
        input_sink: InputSink | None = None,
        clock: Callable[[], float] = time.time,
        monitors_provider: Callable[[], list[MonitorInfo]] = list_monitors,
        virtual_screen_provider: Callable[[], Rect] = virtual_screen,
        windows_provider: Callable[[], list[WindowInfo]] = list_windows,
        cursor_provider: Callable[[], Point | None] = cursor_position,
        popup_provider: Callable[[int], int] = _win32_last_active_popup,
        clipboard_backend: Any = win32_clipboard,
        window_action_fn: Callable[
            [int, WindowActionName, Rect | None], None
        ] = win32_window_action,
        launcher_fn: Callable[[LaunchSpec, list[str] | None], None] = shell_execute,
        uia_provider: ElementProvider | None = None,
        ocr_fn: Callable[[Image.Image, str | None], list[OcrLine]] = ocr_image,
        snip_fn: Callable[[Image.Image, Rect, str | None, float], Rect | None] = run_snip,
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
        self._popup_provider = popup_provider
        self._clipboard_backend = clipboard_backend
        self._window_action_fn = window_action_fn
        self._launcher_fn = launcher_fn
        self._uia_provider = uia_provider
        self._ocr_fn = ocr_fn
        self._snip_fn = snip_fn

        if capture_backends is not None:
            self.capture_backends: dict[str, CaptureBackend] = dict(capture_backends)
        else:
            self.capture_backends = {
                "gdi": GdiBackend(),
                "wgc": WgcBackend(self.cfg),
                "printwindow": PrintWindowBackend(),
            }
        self.input_sink: InputSink = input_sink if input_sink is not None else Win32InputSink()
        self.store = (
            store
            if store is not None
            else ObservationStore(self.cfg.data_dir, self.cfg, clock=self.clock)
        )
        self.capturer = Capturer(
            self.capture_backends,
            self.cfg,
            virtual_screen_provider=self._virtual_screen_provider,
            monitors_provider=self._monitors_provider,
            window_resolver=self._resolve_window,
            window_info_provider=self.window_info,
            hit_test_provider=self._hit_test,
        )
        self.killswitch = KillSwitch(
            self.cfg,
            cursor_provider=self.input_sink.cursor_pos,
            primary_origin=self._primary_origin(),
        )
        self.guard = Guard(
            self.cfg,
            session_provider=self.session_provider,
            killswitch=self.killswitch,
            integrity_at=self._integrity_at,
            self_integrity=self._self_integrity(),
        )

    def _primary_origin(self) -> Point:
        for mon in self._monitors_provider():
            if mon.primary:
                return Point(mon.rect.left, mon.rect.top)
        return Point(0, 0)

    def _self_integrity(self) -> Integrity:
        if isinstance(self.input_sink, FakeInputSink):
            return Integrity.medium
        return self_integrity()

    def _integrity_at(self, p: Point) -> Integrity:
        if isinstance(self.input_sink, FakeInputSink):
            for win in sorted(self._windows_provider(), key=lambda w: w.z_order):
                if win.visible and not win.minimized and win.rect.contains(p):
                    return win.integrity
            return Integrity.medium
        hwnd = root_window_at(p)
        if hwnd == 0:
            return Integrity.medium
        for win in self._windows_provider():
            if win.hwnd == hwnd:
                return win.integrity
        return Integrity.unknown

    def _resolve_window(self, query: str) -> tuple[WindowInfo, list[WindowInfo]]:
        wq = parse_window_query(query)
        return select_window(self._windows_provider(), wq)

    def window_info(self, hwnd: int) -> WindowInfo:
        """Return ``WindowInfo`` for *hwnd* or raise ``WINDOW_NOT_FOUND``."""
        for win in self._windows_provider():
            if win.hwnd == hwnd:
                return win
        raise EdmError(
            ErrorCode.WINDOW_NOT_FOUND,
            f"Window not found: hwnd={hwnd}",
            details={"hwnd": hwnd},
        )

    def last_active_popup(self, hwnd: int) -> int:
        """Return the last active popup window handle for *hwnd*."""
        return self._popup_provider(hwnd)

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
                popup_provider=lambda hwnd: hwnd,
                clipboard_backend=FakeClipboard(),
                window_action_fn=lambda _hwnd, _act, _rect: None,
                launcher_fn=lambda _spec, _args: None,
                uia_provider=FakeUiaProvider(),
                ocr_fn=FakeOcrEngine(),
                snip_fn=FakeSnipSelector(),
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
        parsed = parse_target(target)
        frame, win = self.capturer.capture(parsed, restore=restore)
        edge = max_edge if max_edge is not None else self.cfg.preview_max_edge
        preview = make_preview(frame.image, edge)
        mapping = ImageMapping(
            frame_rect=frame.screen_rect,
            crop=Rect(0, 0, frame.image.width, frame.image.height),
            image_size=preview.size,
        )
        obs_marks: list[Mark] = []
        if marks and win is not None:
            elements, _ = collect_elements(
                win.hwnd,
                timeout_s=self.cfg.uia_timeout_s,
                provider=self._uia_provider,
                screen_bounds=self._virtual_screen_provider(),
            )
            obs_marks = [Mark(id=e.mark, rect=e.rect, label=e.name) for e in elements]
            marks_img = _marks_in_image(obs_marks, mapping)
            if marks_img:
                preview = draw_marks(preview, marks_img)
        if cursor:
            pos = self._cursor_provider()
            if pos is not None and frame.screen_rect.contains(pos):
                preview = draw_cursor(preview, mapping.from_screen(pos))
        if grid:
            preview = draw_grid(preview)

        win_dict: dict[str, Any] | None = None
        if win is not None:
            win_dict = _window_to_dict(win)
            win_dict["last_popup"] = self.last_active_popup(win.hwnd)
        obs = self.store.add(
            frame,
            preview,
            mapping,
            target=target,
            window=win_dict,
            marks=obs_marks,
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
        if not all(math.isfinite(v) for v in (x, y, w, h)):
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                "Zoom coordinates and dimensions must be finite.",
                details={"x": x, "y": y, "w": w, "h": h},
            )
        if factor is not None and (not math.isfinite(factor) or factor <= 0):
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"Zoom factor must be positive and finite, got {factor}.",
                details={"factor": factor},
            )
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
            px_x = min(pw - 1, round(x / 1000.0 * pw))
            px_y = min(ph - 1, round(y / 1000.0 * ph))
            px_w = max(1, min(pw - px_x, round((x + w) / 1000.0 * pw) - px_x))
            px_h = max(1, min(ph - px_y, round((y + h) / 1000.0 * ph) - px_y))
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

    def _log_action(self, action: str, details: dict[str, Any]) -> None:
        now = self.clock()
        day = datetime.fromtimestamp(now).strftime("%Y-%m-%d")
        logs_dir = self.cfg.data_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / f"actions-{day}.jsonl"
        record = {"ts": now, "action": action, "ok": True, "details": details}
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _settle_and_observe(
        self,
        action: str,
        obs: Observation | None,
        *,
        observe: bool,
        details: dict[str, Any],
        warnings: list[str],
    ) -> Result:
        self._log_action(action, details)
        if not observe:
            return Result(
                payload={
                    "ok": True,
                    "action": action,
                    "details": details,
                    "warnings": warnings,
                }
            )

        gdi = self.capture_backends.get("gdi")
        if gdi is not None and gdi.available()[0]:
            vs = self._virtual_screen_provider()
            wait_for_stable(
                lambda: gdi.capture_rect(vs).image,
                self.cfg.settle_quiet_ms,
                self.cfg.settle_timeout_ms,
            )

        target = obs.target if obs is not None else "screen"
        shot = self.screenshot(target=target)
        payload: dict[str, Any] = {
            "ok": True,
            "action": action,
            "observation": shot.payload["observation"],
            "details": {
                **details,
                "foreground_window": shot.payload["details"]["foreground_window"],
            },
            "warnings": warnings,
        }
        return Result(payload=payload, image=shot.image, mime=shot.mime)

    def click(
        self,
        addr: Address,
        button: str = "left",
        count: int = 1,
        modifiers: list[str] | None = None,
        verify: bool = True,
        observe: bool = True,
    ) -> Result:
        """Click at *addr* with preflight, stale checks, and optional observation."""
        mod_vks = parse_chord("+".join(modifiers)) if modifiers else []
        with self.guard.input_lock():
            pt, obs, warnings = resolve_point(self, addr)
            self.guard.preflight(pt)
            if obs is not None:
                check_stale(self, obs, pt, verify=verify)

            try:
                if mod_vks:
                    self.input_sink.send(
                        [ev for vk in mod_vks for ev in key_state_events(vk, "down")]
                    )
                self.input_sink.move_to(pt)
                self.input_sink.send(click_events(button, count))
            finally:
                if mod_vks:
                    self.input_sink.send(
                        [ev for vk in reversed(mod_vks) for ev in key_state_events(vk, "up")]
                    )

            return self._settle_and_observe(
                "click",
                obs,
                observe=observe,
                details={"x": pt.x, "y": pt.y, "button": button, "count": count},
                warnings=warnings,
            )

    def move_mouse(
        self,
        addr: Address,
        verify: bool = True,
        observe: bool = True,
    ) -> Result:
        """Move the mouse cursor to *addr*."""
        with self.guard.input_lock():
            pt, obs, warnings = resolve_point(self, addr)
            self.guard.preflight(pt)
            if obs is not None:
                check_stale(self, obs, pt, verify=verify)
            self.input_sink.move_to(pt)
            return self._settle_and_observe(
                "move_mouse",
                obs,
                observe=observe,
                details={"x": pt.x, "y": pt.y},
                warnings=warnings,
            )

    def drag(
        self,
        from_addr: Address,
        to_addr: Address,
        button: str = "left",
        duration_ms: int = 300,
        verify: bool = True,
        observe: bool = True,
    ) -> Result:
        """Drag from *from_addr* to *to_addr* across 20 interpolated points."""
        if duration_ms < 0:
            raise EdmError(ErrorCode.INVALID_ARGUMENT, "duration_ms must be non-negative.")
        with self.guard.input_lock():
            p1, obs1, w1 = resolve_point(self, from_addr)
            p2, obs2, w2 = resolve_point(self, to_addr)
            self.guard.preflight(p1)
            self.guard.preflight(p2)
            if obs1 is not None:
                check_stale(self, obs1, p1, verify=verify)
            if obs2 is not None and obs2.id != (obs1.id if obs1 else None):
                check_stale(self, obs2, p2, verify=verify)

            pts = interpolate_path([p1, p2], smooth=False, steps_per_segment=20)
            step_sleep = (duration_ms / 1000.0) / max(1, len(pts) - 1)
            try:
                self.input_sink.move_to(pts[0])
                self.input_sink.send(mouse_button_events(button, "down"))
                for pt in pts[1:]:
                    if self.killswitch.triggered():
                        raise EdmError(
                            ErrorCode.ABORTED_BY_USER,
                            "Kill switch triggered during drag.",
                        )
                    self.input_sink.move_to(pt)
                    if step_sleep > 0:
                        time.sleep(step_sleep)
            finally:
                self.input_sink.release_held()

            return self._settle_and_observe(
                "drag",
                obs1 or obs2,
                observe=observe,
                details={"from": [p1.x, p1.y], "to": [p2.x, p2.y], "button": button},
                warnings=w1 + w2,
            )

    def draw_path(
        self,
        observation_id: str,
        points: list[tuple[float, float]],
        coord_space: CoordSpace = "pixel",
        button: str = "left",
        press_button: bool = True,
        smooth: bool = False,
        duration_ms: int = 600,
        observe: bool = True,
    ) -> Result:
        """Move along up to 200 points in *observation_id*, optionally holding *button*."""
        if not points or len(points) > 200:
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"draw_path requires 1 to 200 points, got {len(points)}.",
                details={"count": len(points)},
            )
        if duration_ms < 0:
            raise EdmError(ErrorCode.INVALID_ARGUMENT, "duration_ms must be non-negative.")

        with self.guard.input_lock():
            obs = self.store.get(observation_id)
            screen_pts = [obs.mapping.to_screen(x, y, coord_space) for x, y in points]
            self.guard.preflight(screen_pts[0])
            check_stale(self, obs, screen_pts[0], verify=True)

            path = interpolate_path(screen_pts, smooth=smooth, steps_per_segment=6)
            step_sleep = (duration_ms / 1000.0) / max(1, len(path) - 1)
            try:
                self.input_sink.move_to(path[0])
                if press_button:
                    self.input_sink.send(mouse_button_events(button, "down"))
                for pt in path[1:]:
                    if self.killswitch.triggered():
                        raise EdmError(
                            ErrorCode.ABORTED_BY_USER,
                            "Kill switch triggered during draw_path.",
                        )
                    self.input_sink.move_to(pt)
                    if step_sleep > 0:
                        time.sleep(step_sleep)
            finally:
                self.input_sink.release_held()

            return self._settle_and_observe(
                "draw_path",
                obs,
                observe=observe,
                details={"points": len(points), "interpolated": len(path), "smooth": smooth},
                warnings=[],
            )

    def mouse_button(
        self,
        action: Literal["down", "up"],
        button: str = "left",
        addr: Address | None = None,
        observe: bool = True,
    ) -> Result:
        """Press or release a mouse button, optionally moving to *addr* first."""
        with self.guard.input_lock():
            obs: Observation | None = None
            warnings: list[str] = []
            pt: Point | None = None
            if addr is not None:
                pt, obs, warnings = resolve_point(self, addr)
            self.guard.preflight(pt)
            if obs is not None and pt is not None:
                check_stale(self, obs, pt, verify=True)
            if pt is not None:
                self.input_sink.move_to(pt)
            self.input_sink.send(mouse_button_events(button, action))
            return self._settle_and_observe(
                "mouse_button",
                obs,
                observe=observe,
                details={"action": action, "button": button},
                warnings=warnings,
            )

    def key_state(
        self,
        key: str,
        action: Literal["down", "up"],
        observe: bool = True,
    ) -> Result:
        """Press or release a single key."""
        vks = parse_chord(key)
        if len(vks) != 1:
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"key_state requires a single key, got {key!r}.",
            )
        with self.guard.input_lock():
            self.guard.preflight(None)
            self.input_sink.send(key_state_events(vks[0], action))
            return self._settle_and_observe(
                "key_state",
                None,
                observe=observe,
                details={"key": key, "action": action},
                warnings=[],
            )

    def scroll(
        self,
        addr: Address,
        dy: int = 0,
        dx: int = 0,
        verify: bool = True,
        observe: bool = True,
    ) -> Result:
        """Scroll vertically (*dy*) or horizontally (*dx*) at *addr*."""
        with self.guard.input_lock():
            pt, obs, warnings = resolve_point(self, addr)
            self.guard.preflight(pt)
            if obs is not None:
                check_stale(self, obs, pt, verify=verify)
            self.input_sink.move_to(pt)
            evs = wheel_events(dy=dy, dx=dx)
            if evs:
                self.input_sink.send(evs)
            return self._settle_and_observe(
                "scroll",
                obs,
                observe=observe,
                details={"x": pt.x, "y": pt.y, "dy": dy, "dx": dx},
                warnings=warnings,
            )

    def type_text(
        self,
        text: str,
        interval_ms: int = 0,
        observe: bool = True,
    ) -> Result:
        """Type Unicode *text* via ``KEYEVENTF_UNICODE``."""
        if interval_ms < 0:
            raise EdmError(ErrorCode.INVALID_ARGUMENT, "interval_ms must be non-negative.")
        with self.guard.input_lock():
            self.guard.preflight(None)
            evs = unicode_events(text)
            if interval_ms == 0:
                self.input_sink.send(evs)
            else:
                for i in range(0, len(evs), 2):
                    self.input_sink.send(evs[i : i + 2])
                    if i + 2 < len(evs):
                        time.sleep(interval_ms / 1000.0)
            return self._settle_and_observe(
                "type_text",
                None,
                observe=observe,
                details={"length": len(text)},
                warnings=[],
            )

    def press_keys(
        self,
        keys: str | list[str],
        repeat: int = 1,
        observe: bool = True,
    ) -> Result:
        """Press a key chord string or a sequence of key chords *repeat* times."""
        if repeat < 1:
            raise EdmError(ErrorCode.INVALID_ARGUMENT, "repeat must be >= 1.")
        seq = [keys] if isinstance(keys, str) else list(keys)
        if not seq:
            raise EdmError(ErrorCode.INVALID_ARGUMENT, "keys must not be empty.")
        parsed = [parse_chord(ch) for ch in seq]

        with self.guard.input_lock():
            self.guard.preflight(None)
            for _ in range(repeat):
                for vks in parsed:
                    self.input_sink.send(chord_events(vks))
            return self._settle_and_observe(
                "press_keys",
                None,
                observe=observe,
                details={"keys": seq, "repeat": repeat},
                warnings=[],
            )

    def window_action(
        self,
        window: str,
        action: WindowActionName,
        rect: Rect | None = None,
        observe: bool = True,
    ) -> Result:
        """Perform a window management action on the window matching *window*."""
        with self.guard.input_lock():
            self.guard.preflight(None)
            win, alts = self._resolve_window(window)
            self_int = self._self_integrity()
            if (
                win.integrity == Integrity.unknown
                and integrity_rank(self_int) <= integrity_rank(Integrity.medium)
            ) or integrity_rank(win.integrity) > integrity_rank(self_int):
                raise EdmError(
                    ErrorCode.ELEVATION_REQUIRED,
                    f"Target window hwnd={win.hwnd} is elevated (muhtemelen {win.integrity}); "
                    "run EDM as Administrator.",
                    details={"hwnd": win.hwnd, "target_integrity": str(win.integrity)},
                )
            self._window_action_fn(win.hwnd, action, rect)
            warnings = [f"Multiple windows matched; chose hwnd={win.hwnd}."] if alts else []
            return self._settle_and_observe(
                "window_action",
                None,
                observe=observe,
                details={"hwnd": win.hwnd, "action": action},
                warnings=warnings,
            )

    def launch(
        self,
        target: str,
        args: list[str] | None = None,
        wait_window: str | None = None,
        timeout_s: float = 30.0,
        observe: bool = True,
    ) -> Result:
        """Resolve and launch *target*, optionally waiting for a new matching window."""
        if not math.isfinite(timeout_s) or timeout_s <= 0 or timeout_s > 60.0:
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"timeout_s must be in (0, 60], got {timeout_s}.",
            )
        pattern: re.Pattern[str] | None = None
        if wait_window is not None:
            try:
                pattern = re.compile(wait_window, re.IGNORECASE)
            except re.error as exc:
                raise EdmError(
                    ErrorCode.INVALID_ARGUMENT,
                    f"Invalid wait_window regex: {exc}",
                ) from exc

        self.guard.preflight(None)
        spec = resolve_launch_target(target)
        before_hwnds = {w.hwnd for w in self._windows_provider()}
        self._launcher_fn(spec, args)

        matched_win: WindowInfo | None = None
        if pattern is not None:
            deadline = time.monotonic() + timeout_s
            stable_hwnd: int | None = None
            stable_title: str | None = None
            stable_since: float = 0.0
            while time.monotonic() < deadline:
                cands = [
                    w
                    for w in self._windows_provider()
                    if w.hwnd not in before_hwnds and w.visible and pattern.search(w.title)
                ]
                if cands:
                    cand = cands[0]
                    if cand.hwnd == stable_hwnd and cand.title == stable_title:
                        if time.monotonic() - stable_since >= 1.0:
                            matched_win = cand
                            break
                    else:
                        stable_hwnd = cand.hwnd
                        stable_title = cand.title
                        stable_since = time.monotonic()
                else:
                    stable_hwnd = None
                    stable_title = None
                time.sleep(0.1)
            if matched_win is None:
                raise EdmError(
                    ErrorCode.TIMEOUT,
                    f"Timed out after {timeout_s}s waiting for window matching {wait_window!r}.",
                    details={"wait_window": wait_window},
                )

        details: dict[str, Any] = {
            "spec": {"kind": spec.kind, "value": spec.value},
            "window": _window_to_dict(matched_win) if matched_win is not None else None,
        }
        return self._settle_and_observe(
            "launch",
            None,
            observe=observe,
            details=details,
            warnings=[],
        )

    def wait_for(
        self,
        kind: Literal["change", "stable", "window", "window_gone", "text"],
        target: str = "screen",
        query: str | None = None,
        timeout_s: float = 10.0,
        observe: bool = True,
    ) -> Result:
        """Wait for a screen, window, or text condition up to *timeout_s* (<= 60 s)."""
        if not math.isfinite(timeout_s) or timeout_s <= 0 or timeout_s > 60.0:
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"timeout_s must be in (0, 60], got {timeout_s}.",
                details={"timeout_s": timeout_s},
            )
        if kind == "text":
            if not query:
                raise EdmError(ErrorCode.INVALID_ARGUMENT, "wait_for kind='text' requires query.")
            parsed = parse_target(target)

            def _has_text() -> bool:
                frame, _ = self.capturer.capture(parsed)
                lines = self._ocr_fn(frame.image, None)
                return bool(match_text(lines, query, match="contains"))

            ok = wait_until(_has_text, timeout_s)
            if not ok:
                raise EdmError(
                    ErrorCode.TIMEOUT,
                    f"Timed out after {timeout_s}s waiting for text {query!r}.",
                    details={"kind": kind, "query": query},
                )
            return self._settle_and_observe(
                "wait_for",
                None,
                observe=observe,
                details={"kind": kind, "query": query},
                warnings=[],
            )
        if kind == "stable":
            parsed = parse_target(target)
            wait_for_stable(
                lambda: self.capturer.capture(parsed)[0].image,
                self.cfg.settle_quiet_ms,
                int(timeout_s * 1000),
            )
            return self._settle_and_observe(
                "wait_for", None, observe=observe, details={"kind": kind}, warnings=[]
            )
        if kind == "change":
            parsed = parse_target(target)
            initial = self.capturer.capture(parsed)[0].image
            ok = wait_until(
                lambda: patch_diff(initial, self.capturer.capture(parsed)[0].image) > 0.002,
                timeout_s,
            )
            if not ok:
                raise EdmError(
                    ErrorCode.TIMEOUT,
                    f"Timed out after {timeout_s}s waiting for screen change.",
                )
            return self._settle_and_observe(
                "wait_for", None, observe=observe, details={"kind": kind}, warnings=[]
            )
        if kind in ("window", "window_gone"):
            if not query:
                raise EdmError(
                    ErrorCode.INVALID_ARGUMENT,
                    f"wait_for kind={kind!r} requires query.",
                )
            wq = parse_window_query(query)
            if kind == "window":
                ok = wait_until(
                    lambda: any(_matches_query(w, wq) for w in self._windows_provider()),
                    timeout_s,
                )
            else:
                ok = wait_until(
                    lambda: not any(_matches_query(w, wq) for w in self._windows_provider()),
                    timeout_s,
                )
            if not ok:
                raise EdmError(
                    ErrorCode.TIMEOUT,
                    f"Timed out after {timeout_s}s waiting for {kind} ({query!r}).",
                    details={"kind": kind, "query": query},
                )
            return self._settle_and_observe(
                "wait_for",
                None,
                observe=observe,
                details={"kind": kind, "query": query},
                warnings=[],
            )
        raise EdmError(ErrorCode.INVALID_ARGUMENT, f"Unsupported wait_for kind: {kind!r}")

    def clipboard(
        self,
        op: Literal["get", "set"],
        text: str | None = None,
    ) -> Result:
        """Get or set clipboard contents."""
        if op == "get":
            txt = self._clipboard_backend.get_text()
            img = self._clipboard_backend.get_image()
            return Result(
                payload={
                    "ok": True,
                    "action": "clipboard",
                    "op": "get",
                    "text": txt,
                    "has_image": img is not None,
                    "details": {},
                    "warnings": [],
                }
            )
        if op == "set":
            if text is None:
                raise EdmError(
                    ErrorCode.INVALID_ARGUMENT,
                    "clipboard op='set' requires text.",
                )
            self._clipboard_backend.set_text(text)
            return Result(
                payload={
                    "ok": True,
                    "action": "clipboard",
                    "op": "set",
                    "length": len(text),
                    "details": {},
                    "warnings": [],
                }
            )
        raise EdmError(ErrorCode.INVALID_ARGUMENT, f"Unsupported clipboard op: {op!r}")

    def run_sequence(
        self,
        steps: list[Step] | list[dict[str, Any]],
        stop_on_error: bool = True,
    ) -> Result:
        """Validate and execute a multi-step action sequence."""
        return execute_sequence(self, steps, stop_on_error=stop_on_error)

    def ui_elements(
        self,
        window: str | None = None,
        max_elements: int = 150,
    ) -> Result:
        """Collect UIA interactive elements for *window* (or foreground) with Set-of-Mark."""
        if window is not None:
            win, _ = self._resolve_window(window)
        else:
            cands = [w for w in self._windows_provider() if w.visible and not w.minimized]
            if not cands:
                raise EdmError(ErrorCode.WINDOW_NOT_FOUND, "No visible window found.")
            fg = [w for w in cands if w.foreground]
            win = fg[0] if fg else sorted(cands, key=lambda w: w.z_order)[0]

        target_str = f"window:hwnd:{win.hwnd}"
        frame, _ = self.capturer.capture(parse_target(target_str))
        elements, truncated = collect_elements(
            win.hwnd,
            max_elements=max_elements,
            timeout_s=self.cfg.uia_timeout_s,
            provider=self._uia_provider,
            screen_bounds=self._virtual_screen_provider(),
        )
        preview = make_preview(frame.image, self.cfg.preview_max_edge)
        mapping = ImageMapping(
            frame_rect=frame.screen_rect,
            crop=Rect(0, 0, frame.image.width, frame.image.height),
            image_size=preview.size,
        )
        obs_marks = [Mark(id=e.mark, rect=e.rect, label=e.name) for e in elements]
        marks_img = _marks_in_image(obs_marks, mapping)
        if marks_img:
            preview = draw_marks(preview, marks_img)

        win_dict = _window_to_dict(win)
        win_dict["last_popup"] = self.last_active_popup(win.hwnd)
        obs = self.store.add(
            frame,
            preview,
            mapping,
            target=target_str,
            window=win_dict,
            marks=obs_marks,
        )
        img_bytes, mime = encode_image(preview, self.cfg.max_image_bytes)
        return Result(
            payload={
                "ok": True,
                "action": "ui_elements",
                "observation": obs.to_public(),
                "details": {
                    "elements": [_element_to_dict(e) for e in elements],
                    "truncated": truncated,
                },
                "warnings": [],
            },
            image=img_bytes,
            mime=mime,
        )

    def find_text(
        self,
        query: str,
        target: str = "screen",
        match: MatchMode = "contains",
    ) -> Result:
        """Capture *target* and search for *query* via offline Windows OCR."""
        if not query:
            raise EdmError(ErrorCode.INVALID_ARGUMENT, "find_text query must not be empty.")
        parsed = parse_target(target)
        frame, win = self.capturer.capture(parsed)
        lines = self._ocr_fn(frame.image, None)
        matches = match_text(lines, query, match=match)

        preview = make_preview(frame.image, self.cfg.preview_max_edge)
        mapping = ImageMapping(
            frame_rect=frame.screen_rect,
            crop=Rect(0, 0, frame.image.width, frame.image.height),
            image_size=preview.size,
        )
        win_dict = _window_to_dict(win) if win is not None else None
        if win_dict is not None and win is not None:
            win_dict["last_popup"] = self.last_active_popup(win.hwnd)
        obs = self.store.add(frame, preview, mapping, target=target, window=win_dict)
        img_bytes, mime = encode_image(preview, self.cfg.max_image_bytes)

        ox, oy = frame.screen_rect.left, frame.screen_rect.top
        match_dicts = []
        for m in matches:
            sx1, sy1 = ox + m.rect_image.left, oy + m.rect_image.top
            sx2, sy2 = ox + m.rect_image.right, oy + m.rect_image.bottom
            ix1, iy1 = mapping.from_screen(Point(sx1, sy1))
            ix2, iy2 = mapping.from_screen(Point(sx2, sy2))
            match_dicts.append(
                {
                    "text": m.text,
                    "rect_image": [round(ix1), round(iy1), round(ix2), round(iy2)],
                    "rect_screen": [sx1, sy1, sx2, sy2],
                }
            )
        return Result(
            payload={
                "ok": True,
                "action": "find_text",
                "observation": obs.to_public(),
                "details": {"matches": match_dicts, "query": query, "match": match},
                "warnings": [],
            },
            image=img_bytes,
            mime=mime,
        )

    def request_user_region(
        self,
        prompt: str | None = None,
        timeout_s: float = 120.0,
    ) -> Result:
        """Freeze the virtual screen and let the user drag-select a region."""
        if not math.isfinite(timeout_s) or timeout_s <= 0:
            raise EdmError(ErrorCode.INVALID_ARGUMENT, "timeout_s must be positive and finite.")
        frame, _ = self.capturer.capture(CaptureTarget(kind="screen"))
        vs = frame.screen_rect
        selected = self._snip_fn(frame.image, vs, prompt, timeout_s)
        if selected is None:
            return Result(
                payload={
                    "ok": True,
                    "action": "request_user_region",
                    "details": {"cancelled": True},
                    "warnings": [],
                }
            )
        clipped = selected.intersection(vs)
        if clipped is None or clipped.width <= 0 or clipped.height <= 0:
            return Result(
                payload={
                    "ok": True,
                    "action": "request_user_region",
                    "details": {"cancelled": True},
                    "warnings": [],
                }
            )
        crop_box = (
            clipped.left - vs.left,
            clipped.top - vs.top,
            clipped.right - vs.left,
            clipped.bottom - vs.top,
        )
        cropped_img = frame.image.crop(crop_box)
        sub_frame = Frame(
            image=cropped_img,
            screen_rect=clipped,
            backend=frame.backend,
            captured_at=self.clock(),
            attempts=frame.attempts,
        )
        preview = make_preview(cropped_img, self.cfg.preview_max_edge)
        mapping = ImageMapping(
            frame_rect=clipped,
            crop=Rect(0, 0, cropped_img.width, cropped_img.height),
            image_size=preview.size,
        )
        target_str = f"region:{clipped.left},{clipped.top},{clipped.width},{clipped.height}"
        obs = self.store.add(
            sub_frame,
            preview,
            mapping,
            target=target_str,
            tags=("user_snip",),
        )
        img_bytes, mime = encode_image(preview, self.cfg.max_image_bytes)
        return Result(
            payload={
                "ok": True,
                "action": "request_user_region",
                "observation": obs.to_public(),
                "details": {"cancelled": False},
                "warnings": [],
            },
            image=img_bytes,
            mime=mime,
        )

    def get_user_snips(self, limit: int = 1) -> Result:
        """Return recent user-snipped observations, newest first."""
        if limit < 0:
            raise EdmError(ErrorCode.INVALID_ARGUMENT, "limit must be non-negative.")
        snips = self.store.list_by_tag("user_snip", limit=limit)
        return Result(
            payload={
                "ok": True,
                "action": "get_user_snips",
                "snips": [s.to_public() for s in snips],
                "details": {"count": len(snips)},
                "warnings": [],
            }
        )

    def prune(self) -> Result:
        """Prune expired or over-budget observations from the store."""
        deleted = self.store.prune()
        return Result(
            payload={
                "ok": True,
                "action": "prune",
                "deleted": deleted,
                "details": {"deleted": deleted},
                "warnings": [],
            }
        )
