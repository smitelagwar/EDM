"""Win32 window enumeration, query parsing, and selection."""

from __future__ import annotations

import ctypes
import re
from ctypes import wintypes
from dataclasses import dataclass
from typing import Literal

from edm.errors import EdmError, ErrorCode
from edm.geometry import Point, Rect
from edm.perception.textnorm import tr_fold
from edm.win32.api import (
    DWMWA_CLOAKED,
    DWMWA_EXTENDED_FRAME_BOUNDS,
    DwmGetWindowAttribute,
    GetWindowRect,
    user32,
)
from edm.win32.monitors import MonitorInfo, list_monitors
from edm.win32.process import Integrity, process_exe, process_integrity

_GW_OWNER = 4
_GWL_EXSTYLE = -20
_WS_EX_TOPMOST = 0x00000008
_GA_ROOT = 2

_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

_EnumWindows = user32.EnumWindows
_EnumWindows.argtypes = [_WNDENUMPROC, wintypes.LPARAM]
_EnumWindows.restype = wintypes.BOOL

_IsWindow = user32.IsWindow
_IsWindow.argtypes = [wintypes.HWND]
_IsWindow.restype = wintypes.BOOL

_IsWindowVisible = user32.IsWindowVisible
_IsWindowVisible.argtypes = [wintypes.HWND]
_IsWindowVisible.restype = wintypes.BOOL

_IsIconic = user32.IsIconic
_IsIconic.argtypes = [wintypes.HWND]
_IsIconic.restype = wintypes.BOOL

_IsZoomed = user32.IsZoomed
_IsZoomed.argtypes = [wintypes.HWND]
_IsZoomed.restype = wintypes.BOOL

_GetWindowTextLengthW = user32.GetWindowTextLengthW
_GetWindowTextLengthW.argtypes = [wintypes.HWND]
_GetWindowTextLengthW.restype = ctypes.c_int

_GetWindowTextW = user32.GetWindowTextW
_GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_GetWindowTextW.restype = ctypes.c_int

_GetClassNameW = user32.GetClassNameW
_GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_GetClassNameW.restype = ctypes.c_int

_GetWindow = user32.GetWindow
_GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
_GetWindow.restype = wintypes.HWND

_GetWindowLongPtrW = user32.GetWindowLongPtrW
_GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
_GetWindowLongPtrW.restype = ctypes.c_ssize_t

_GetWindowThreadProcessId = user32.GetWindowThreadProcessId
_GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_GetWindowThreadProcessId.restype = wintypes.DWORD

_GetForegroundWindow = user32.GetForegroundWindow
_GetForegroundWindow.argtypes = []
_GetForegroundWindow.restype = wintypes.HWND

_WindowFromPoint = user32.WindowFromPoint
_WindowFromPoint.argtypes = [wintypes.POINT]
_WindowFromPoint.restype = wintypes.HWND

_GetAncestor = user32.GetAncestor
_GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
_GetAncestor.restype = wintypes.HWND


@dataclass(frozen=True)
class WindowInfo:
    """Metadata for a top-level Win32 window."""

    hwnd: int
    title: str
    class_name: str
    pid: int
    exe: str
    rect: Rect
    minimized: bool
    maximized: bool
    visible: bool
    cloaked: bool
    topmost: bool
    foreground: bool
    monitor_index: int
    integrity: Integrity
    z_order: int


@dataclass(frozen=True)
class WindowQuery:
    """Parsed window selector query."""

    kind: Literal["hwnd", "pid", "exe", "class", "title", "regex", "text"]
    value: str


def parse_window_query(q: str) -> WindowQuery:
    """Parse a window selector string into a structured ``WindowQuery``."""
    stripped = q.strip()
    if not stripped:
        raise EdmError(ErrorCode.INVALID_ARGUMENT, "Window query must not be empty.")

    lowered = stripped.lower()
    if lowered.startswith("hwnd:"):
        raw = stripped[5:].strip()
        try:
            val = int(raw, 0)
        except ValueError as exc:
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"Invalid hwnd in window query: {raw!r}",
            ) from exc
        if val <= 0:
            raise EdmError(ErrorCode.INVALID_ARGUMENT, f"hwnd must be positive: {val}")
        return WindowQuery(kind="hwnd", value=str(val))

    if lowered.startswith("pid:"):
        raw = stripped[4:].strip()
        try:
            val = int(raw)
        except ValueError as exc:
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"Invalid pid in window query: {raw!r}",
            ) from exc
        if val <= 0:
            raise EdmError(ErrorCode.INVALID_ARGUMENT, f"pid must be positive: {val}")
        return WindowQuery(kind="pid", value=str(val))

    if lowered.startswith("exe:"):
        raw = stripped[4:].strip()
        if not raw:
            raise EdmError(ErrorCode.INVALID_ARGUMENT, "exe query value must not be empty.")
        return WindowQuery(kind="exe", value=raw.lower())

    if lowered.startswith("class:"):
        raw = stripped[6:].strip()
        if not raw:
            raise EdmError(ErrorCode.INVALID_ARGUMENT, "class query value must not be empty.")
        return WindowQuery(kind="class", value=raw)

    if lowered.startswith("title:"):
        raw = stripped[6:].strip()
        if not raw:
            raise EdmError(ErrorCode.INVALID_ARGUMENT, "title query value must not be empty.")
        return WindowQuery(kind="title", value=raw)

    if lowered.startswith("re:"):
        raw = stripped[3:]
        if not raw:
            raise EdmError(ErrorCode.INVALID_ARGUMENT, "regex query value must not be empty.")
        try:
            re.compile(raw)
        except re.error as exc:
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"Invalid regex in window query: {exc}",
            ) from exc
        return WindowQuery(kind="regex", value=raw)

    return WindowQuery(kind="text", value=stripped)


def _matches_query(win: WindowInfo, q: WindowQuery) -> bool:
    if q.kind == "hwnd":
        return win.hwnd == int(q.value)
    if q.kind == "pid":
        return win.pid == int(q.value)
    if q.kind == "exe":
        return win.exe.casefold() == q.value.casefold()
    if q.kind == "class":
        return win.class_name.casefold() == q.value.casefold()
    if q.kind in ("title", "text"):
        return tr_fold(q.value) in tr_fold(win.title)
    if q.kind == "regex":
        return re.search(q.value, win.title, re.IGNORECASE) is not None
    return False


def select_window(
    cands: list[WindowInfo],
    q: WindowQuery,
) -> tuple[WindowInfo, list[WindowInfo]]:
    """Select the topmost matching window and return remaining alternatives."""
    matches = [w for w in cands if _matches_query(w, q)]
    if not matches:
        raise EdmError(
            ErrorCode.WINDOW_NOT_FOUND,
            f"No window matched query {q.kind}:{q.value}",
            details={"kind": q.kind, "value": q.value},
        )
    ordered = sorted(matches, key=lambda w: w.z_order)
    return ordered[0], ordered[1:]


def _window_title(hwnd: int) -> str:
    length = int(_GetWindowTextLengthW(hwnd))
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    _GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _window_class(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    _GetClassNameW(hwnd, buf, 256)
    return buf.value


def _window_rect(hwnd: int) -> Rect:
    rc = wintypes.RECT()
    hr = DwmGetWindowAttribute(
        hwnd,
        DWMWA_EXTENDED_FRAME_BOUNDS,
        ctypes.byref(rc),
        ctypes.sizeof(rc),
    )
    if hr != 0:
        GetWindowRect(hwnd, ctypes.byref(rc))
    return Rect(int(rc.left), int(rc.top), int(rc.right), int(rc.bottom))


def _is_cloaked(hwnd: int) -> bool:
    cloaked = wintypes.DWORD(0)
    hr = DwmGetWindowAttribute(
        hwnd,
        DWMWA_CLOAKED,
        ctypes.byref(cloaked),
        ctypes.sizeof(cloaked),
    )
    return hr == 0 and cloaked.value != 0


def _monitor_for_rect(rect: Rect, monitors: list[MonitorInfo]) -> int:
    if not monitors:
        return 0
    center = rect.center
    for mon in monitors:
        if mon.rect.contains(center):
            return mon.index
    best_idx = monitors[0].index
    best_area = -1
    for mon in monitors:
        inter = rect.intersection(mon.rect)
        if inter is not None:
            area = inter.width * inter.height
            if area > best_area:
                best_area = area
                best_idx = mon.index
    return best_idx


def _build_window_info(
    hwnd: int,
    z_order: int,
    fg_hwnd: int,
    monitors: list[MonitorInfo],
) -> WindowInfo:
    pid_val = wintypes.DWORD(0)
    _GetWindowThreadProcessId(hwnd, ctypes.byref(pid_val))
    pid = int(pid_val.value)
    rect = _window_rect(hwnd)
    ex_style = int(_GetWindowLongPtrW(hwnd, _GWL_EXSTYLE))
    return WindowInfo(
        hwnd=hwnd,
        title=_window_title(hwnd),
        class_name=_window_class(hwnd),
        pid=pid,
        exe=process_exe(pid),
        rect=rect,
        minimized=bool(_IsIconic(hwnd)),
        maximized=bool(_IsZoomed(hwnd)),
        visible=bool(_IsWindowVisible(hwnd)),
        cloaked=_is_cloaked(hwnd),
        topmost=bool(ex_style & _WS_EX_TOPMOST),
        foreground=(hwnd == fg_hwnd),
        monitor_index=_monitor_for_rect(rect, monitors),
        integrity=process_integrity(pid),
        z_order=z_order,
    )


def list_windows(
    include_minimized: bool = True,
    include_cloaked: bool = False,
) -> list[WindowInfo]:
    """Enumerate visible top-level unowned windows in Z-order."""
    hwnds: list[int] = []

    def _cb(hwnd: int, _lparam: int) -> bool:
        if not _IsWindowVisible(hwnd):
            return True
        if _GetWindow(hwnd, _GW_OWNER):
            return True
        hwnds.append(int(hwnd))
        return True

    cb = _WNDENUMPROC(_cb)
    _EnumWindows(cb, 0)

    fg_hwnd = int(_GetForegroundWindow() or 0)
    monitors = list_monitors()
    result: list[WindowInfo] = []
    z_order = 0
    for hwnd in hwnds:
        info = _build_window_info(hwnd, z_order, fg_hwnd, monitors)
        if info.cloaked and not include_cloaked:
            continue
        if info.minimized and not include_minimized:
            continue
        result.append(info)
        z_order += 1
    return result


def window_info(hwnd: int) -> WindowInfo:
    """Return ``WindowInfo`` for *hwnd*, raising ``WINDOW_NOT_FOUND`` if invalid."""
    if hwnd <= 0 or not _IsWindow(hwnd):
        raise EdmError(
            ErrorCode.WINDOW_NOT_FOUND,
            f"Window not found: hwnd={hwnd}",
            details={"hwnd": hwnd},
        )
    fg_hwnd = int(_GetForegroundWindow() or 0)
    monitors = list_monitors()
    return _build_window_info(hwnd, 0, fg_hwnd, monitors)


def resolve_window(q: str) -> tuple[WindowInfo, list[WindowInfo]]:
    """Parse *q* and select the matching topmost window from visible windows."""
    wq = parse_window_query(q)
    return select_window(list_windows(include_minimized=True, include_cloaked=False), wq)


def root_window_at(p: Point) -> int:
    """Return the root ancestor window handle at screen point *p*, or 0."""
    pt = wintypes.POINT(p.x, p.y)
    hwnd = _WindowFromPoint(pt)
    if not hwnd:
        return 0
    root = _GetAncestor(hwnd, _GA_ROOT)
    return int(root or hwnd)
