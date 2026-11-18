"""Win32 DLL handles and explicit ctypes function prototypes."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
shcore = ctypes.WinDLL("shcore", use_last_error=True)

DPI_AWARENESS_CONTEXT = wintypes.HANDLE
DPI_AWARENESS_CONTEXT_UNAWARE = DPI_AWARENESS_CONTEXT(-1)
DPI_AWARENESS_CONTEXT_SYSTEM_AWARE = DPI_AWARENESS_CONTEXT(-2)
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE = DPI_AWARENESS_CONTEXT(-3)
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = DPI_AWARENESS_CONTEXT(-4)
DPI_AWARENESS_CONTEXT_UNAWARE_GDISCALED = DPI_AWARENESS_CONTEXT(-5)

DPI_AWARENESS_INVALID = -1
DPI_AWARENESS_UNAWARE = 0
DPI_AWARENESS_SYSTEM_AWARE = 1
DPI_AWARENESS_PER_MONITOR_AWARE = 2

MDT_EFFECTIVE_DPI = 0
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14

# user32: Input & Windows
SendInput = user32.SendInput
SendInput.argtypes = [wintypes.UINT, ctypes.c_void_p, ctypes.c_int]
SendInput.restype = wintypes.UINT

GetWindowRect = user32.GetWindowRect
GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
GetWindowRect.restype = wintypes.BOOL

# user32: DPI awareness
SetProcessDpiAwarenessContext = user32.SetProcessDpiAwarenessContext
SetProcessDpiAwarenessContext.argtypes = [DPI_AWARENESS_CONTEXT]
SetProcessDpiAwarenessContext.restype = wintypes.BOOL

GetThreadDpiAwarenessContext = user32.GetThreadDpiAwarenessContext
GetThreadDpiAwarenessContext.argtypes = []
GetThreadDpiAwarenessContext.restype = DPI_AWARENESS_CONTEXT

GetAwarenessFromDpiAwarenessContext = user32.GetAwarenessFromDpiAwarenessContext
GetAwarenessFromDpiAwarenessContext.argtypes = [DPI_AWARENESS_CONTEXT]
GetAwarenessFromDpiAwarenessContext.restype = ctypes.c_int

AreDpiAwarenessContextsEqual = user32.AreDpiAwarenessContextsEqual
AreDpiAwarenessContextsEqual.argtypes = [DPI_AWARENESS_CONTEXT, DPI_AWARENESS_CONTEXT]
AreDpiAwarenessContextsEqual.restype = wintypes.BOOL

IsProcessDPIAware = user32.IsProcessDPIAware
IsProcessDPIAware.argtypes = []
IsProcessDPIAware.restype = wintypes.BOOL

# dwmapi
DwmGetWindowAttribute = dwmapi.DwmGetWindowAttribute
DwmGetWindowAttribute.argtypes = [
    wintypes.HWND,
    wintypes.DWORD,
    ctypes.c_void_p,
    wintypes.DWORD,
]
DwmGetWindowAttribute.restype = ctypes.HRESULT

# shcore
GetDpiForMonitor = shcore.GetDpiForMonitor
GetDpiForMonitor.argtypes = [
    wintypes.HMONITOR,
    ctypes.c_int,
    ctypes.POINTER(wintypes.UINT),
    ctypes.POINTER(wintypes.UINT),
]
GetDpiForMonitor.restype = ctypes.HRESULT

# kernel32
GetCurrentProcessId = kernel32.GetCurrentProcessId
GetCurrentProcessId.argtypes = []
GetCurrentProcessId.restype = wintypes.DWORD

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL

__all__ = [
    "AreDpiAwarenessContextsEqual",
    "CloseHandle",
    "DPI_AWARENESS_CONTEXT",
    "DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE",
    "DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2",
    "DPI_AWARENESS_CONTEXT_SYSTEM_AWARE",
    "DPI_AWARENESS_CONTEXT_UNAWARE",
    "DPI_AWARENESS_CONTEXT_UNAWARE_GDISCALED",
    "DPI_AWARENESS_INVALID",
    "DPI_AWARENESS_PER_MONITOR_AWARE",
    "DPI_AWARENESS_SYSTEM_AWARE",
    "DPI_AWARENESS_UNAWARE",
    "DWMWA_CLOAKED",
    "DWMWA_EXTENDED_FRAME_BOUNDS",
    "DwmGetWindowAttribute",
    "GetAwarenessFromDpiAwarenessContext",
    "GetCurrentProcessId",
    "GetDpiForMonitor",
    "GetThreadDpiAwarenessContext",
    "GetWindowRect",
    "IsProcessDPIAware",
    "MDT_EFFECTIVE_DPI",
    "SendInput",
    "SetProcessDpiAwarenessContext",
    "advapi32",
    "dwmapi",
    "gdi32",
    "kernel32",
    "shcore",
    "user32",
]
