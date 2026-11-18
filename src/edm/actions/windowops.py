"""Win32 window focus, state, move, resize, and close operations."""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from typing import Literal

from edm.errors import EdmError, ErrorCode
from edm.geometry import Rect
from edm.win32.api import kernel32, user32

WindowActionName = Literal[
    "focus",
    "minimize",
    "maximize",
    "restore",
    "close",
    "move",
    "resize",
]

_SW_MAXIMIZE = 3
_SW_MINIMIZE = 6
_SW_RESTORE = 9
_WM_CLOSE = 0x0010
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOZORDER = 0x0004

_IsIconic = user32.IsIconic
_IsIconic.argtypes = [wintypes.HWND]
_IsIconic.restype = wintypes.BOOL

_ShowWindow = user32.ShowWindow
_ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
_ShowWindow.restype = wintypes.BOOL

_SetForegroundWindow = user32.SetForegroundWindow
_SetForegroundWindow.argtypes = [wintypes.HWND]
_SetForegroundWindow.restype = wintypes.BOOL

_GetForegroundWindow = user32.GetForegroundWindow
_GetForegroundWindow.argtypes = []
_GetForegroundWindow.restype = wintypes.HWND

_BringWindowToTop = user32.BringWindowToTop
_BringWindowToTop.argtypes = [wintypes.HWND]
_BringWindowToTop.restype = wintypes.BOOL

_GetWindowThreadProcessId = user32.GetWindowThreadProcessId
_GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_GetWindowThreadProcessId.restype = wintypes.DWORD

_GetCurrentThreadId = kernel32.GetCurrentThreadId
_GetCurrentThreadId.argtypes = []
_GetCurrentThreadId.restype = wintypes.DWORD

_AttachThreadInput = user32.AttachThreadInput
_AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
_AttachThreadInput.restype = wintypes.BOOL

_PostMessageW = user32.PostMessageW
_PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_PostMessageW.restype = wintypes.BOOL

_SetWindowPos = user32.SetWindowPos
_SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
_SetWindowPos.restype = wintypes.BOOL


def focus_window(hwnd: int) -> bool:
    """Restore if minimized and bring *hwnd* to the foreground (verifying <= 1 s)."""
    if _IsIconic(hwnd):
        _ShowWindow(hwnd, _SW_RESTORE)

    _SetForegroundWindow(hwnd)
    if int(_GetForegroundWindow() or 0) != hwnd:
        fg_hwnd = int(_GetForegroundWindow() or 0)
        fg_tid = int(_GetWindowThreadProcessId(fg_hwnd, None)) if fg_hwnd else 0
        cur_tid = int(_GetCurrentThreadId())
        if fg_tid and fg_tid != cur_tid:
            _AttachThreadInput(cur_tid, fg_tid, True)
            try:
                _BringWindowToTop(hwnd)
                _SetForegroundWindow(hwnd)
            finally:
                _AttachThreadInput(cur_tid, fg_tid, False)
        else:
            _BringWindowToTop(hwnd)
            _SetForegroundWindow(hwnd)

    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        if int(_GetForegroundWindow() or 0) == hwnd:
            return True
        time.sleep(0.05)
    return int(_GetForegroundWindow() or 0) == hwnd


def window_action(
    hwnd: int,
    action: WindowActionName,
    rect: Rect | None = None,
) -> None:
    """Execute a window management action on *hwnd*."""
    if action == "focus":
        focus_window(hwnd)
        return
    if action == "minimize":
        _ShowWindow(hwnd, _SW_MINIMIZE)
        return
    if action == "maximize":
        _ShowWindow(hwnd, _SW_MAXIMIZE)
        return
    if action == "restore":
        _ShowWindow(hwnd, _SW_RESTORE)
        return
    if action == "close":
        _PostMessageW(hwnd, _WM_CLOSE, 0, 0)
        return
    if action == "move":
        if rect is None:
            raise EdmError(ErrorCode.INVALID_ARGUMENT, "window_action 'move' requires rect.")
        _SetWindowPos(hwnd, 0, rect.left, rect.top, 0, 0, _SWP_NOSIZE | _SWP_NOZORDER)
        return
    if action == "resize":
        if rect is None:
            raise EdmError(ErrorCode.INVALID_ARGUMENT, "window_action 'resize' requires rect.")
        if rect.width <= 0 or rect.height <= 0:
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"Resize dimensions must be positive, got {(rect.width, rect.height)}.",
            )
        _SetWindowPos(hwnd, 0, 0, 0, rect.width, rect.height, _SWP_NOMOVE | _SWP_NOZORDER)
        return
    raise EdmError(
        ErrorCode.INVALID_ARGUMENT,
        f"Unsupported window action: {action!r}",
        details={"action": action},
    )
