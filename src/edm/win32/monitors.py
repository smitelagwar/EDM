"""Win32 monitor enumeration and virtual screen bounds."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any

from edm.geometry import Rect

_MONITORINFOF_PRIMARY = 1
_MDT_EFFECTIVE_DPI = 0
_SM_XVIRTUALSCREEN = 76
_SM_YVIRTUALSCREEN = 77
_SM_CXVIRTUALSCREEN = 78
_SM_CYVIRTUALSCREEN = 79


class _MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * 32),
    ]


_MONITORENUMPROC = ctypes.WINFUNCTYPE(
    wintypes.BOOL,
    wintypes.HMONITOR,
    wintypes.HDC,
    ctypes.POINTER(wintypes.RECT),
    wintypes.LPARAM,
)


@dataclass(frozen=True)
class MonitorInfo:
    """Metadata for a single physical display monitor."""

    index: int
    device: str
    rect: Rect
    work_rect: Rect
    dpi: int
    scale: float
    primary: bool


def _rect_from_win32(rc: wintypes.RECT) -> Rect:
    return Rect(int(rc.left), int(rc.top), int(rc.right), int(rc.bottom))


def _query_monitor_dpi(hmon: int) -> int:
    try:
        shcore = ctypes.windll.shcore
    except OSError:
        return 96
    dpi_x = ctypes.c_uint(96)
    dpi_y = ctypes.c_uint(96)
    try:
        hr = shcore.GetDpiForMonitor(
            wintypes.HMONITOR(hmon),
            _MDT_EFFECTIVE_DPI,
            ctypes.byref(dpi_x),
            ctypes.byref(dpi_y),
        )
    except (AttributeError, OSError):
        return 96
    if hr != 0 or dpi_x.value <= 0:
        return 96
    return int(dpi_x.value)


def list_monitors() -> list[MonitorInfo]:
    """Enumerate display monitors, primary at index 0 and others sorted left-to-right."""
    user32 = ctypes.windll.user32
    raw: list[tuple[str, Rect, Rect, int, bool]] = []

    def _callback(hmon: int, _hdc: int, _lprc: Any, _lparam: int) -> bool:
        info = _MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(_MONITORINFOEXW)
        if user32.GetMonitorInfoW(wintypes.HMONITOR(hmon), ctypes.byref(info)):
            raw.append(
                (
                    str(info.szDevice),
                    _rect_from_win32(info.rcMonitor),
                    _rect_from_win32(info.rcWork),
                    _query_monitor_dpi(hmon),
                    bool(info.dwFlags & _MONITORINFOF_PRIMARY),
                )
            )
        return True

    proc = _MONITORENUMPROC(_callback)
    user32.EnumDisplayMonitors(None, None, proc, 0)

    raw.sort(key=lambda item: (not item[4], item[1].left, item[1].top, item[0]))
    return [
        MonitorInfo(
            index=idx,
            device=device,
            rect=rect,
            work_rect=work_rect,
            dpi=dpi,
            scale=dpi / 96.0,
            primary=primary,
        )
        for idx, (device, rect, work_rect, dpi, primary) in enumerate(raw)
    ]


def virtual_screen() -> Rect:
    """Return the bounding rectangle of the entire Windows virtual screen."""
    user32 = ctypes.windll.user32
    left = int(user32.GetSystemMetrics(_SM_XVIRTUALSCREEN))
    top = int(user32.GetSystemMetrics(_SM_YVIRTUALSCREEN))
    width = int(user32.GetSystemMetrics(_SM_CXVIRTUALSCREEN))
    height = int(user32.GetSystemMetrics(_SM_CYVIRTUALSCREEN))
    if width > 0 and height > 0:
        return Rect.from_xywh(left, top, width, height)

    monitors = list_monitors()
    if not monitors:
        return Rect(0, 0, 0, 0)
    return Rect(
        left=min(m.rect.left for m in monitors),
        top=min(m.rect.top for m in monitors),
        right=max(m.rect.right for m in monitors),
        bottom=max(m.rect.bottom for m in monitors),
    )
