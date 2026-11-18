"""Win32 window station, desktop, and lock-state classification."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from typing import Literal

SessionState = Literal["ok", "isolated_desktop", "secure_desktop", "session_locked"]

_UOI_NAME = 2
_DESKTOP_READOBJECTS = 0x0001
_WTS_CURRENT_SERVER_HANDLE = None
_WTS_CURRENT_SESSION = 0xFFFFFFFF
_WTS_SESSION_INFO_EX = 25
_WTS_SESSIONSTATE_LOCK = 0


class _WTSINFOEX_LEVEL1_W(ctypes.Structure):
    _fields_ = [
        ("SessionId", wintypes.ULONG),
        ("SessionState", wintypes.INT),
        ("SessionFlags", wintypes.LONG),
        ("WinStationName", wintypes.WCHAR * 33),
        ("UserName", wintypes.WCHAR * 21),
        ("DomainName", wintypes.WCHAR * 18),
        ("LogonTime", ctypes.c_int64),
        ("ConnectTime", ctypes.c_int64),
        ("DisconnectTime", ctypes.c_int64),
        ("LastInputTime", ctypes.c_int64),
        ("CurrentTime", ctypes.c_int64),
        ("IncomingBytes", wintypes.DWORD),
        ("OutgoingBytes", wintypes.DWORD),
        ("IncomingFrames", wintypes.DWORD),
        ("OutgoingFrames", wintypes.DWORD),
        ("IncomingCompressedBytes", wintypes.DWORD),
        ("OutgoingCompressedBytes", wintypes.DWORD),
    ]


class _WTSINFOEXW(ctypes.Structure):
    _fields_ = [
        ("Level", wintypes.DWORD),
        ("Data", _WTSINFOEX_LEVEL1_W),
    ]


@dataclass(frozen=True)
class SessionInfo:
    """Snapshot of the current process window station, desktops, and lock state."""

    station: str
    thread_desktop: str
    input_desktop: str | None
    state: SessionState


def classify_session(
    station: str,
    thread_desktop: str,
    input_desktop: str | None,
    locked: bool = False,
) -> SessionState:
    """Classify the desktop session state from station, desktops, and lock status."""
    if station.lower() != "winsta0":
        return "isolated_desktop"
    if thread_desktop.lower() != "default":
        return "isolated_desktop"
    if locked:
        return "session_locked"
    if input_desktop is None or input_desktop.lower() != "default":
        return "secure_desktop"
    return "ok"


def _query_object_name(user32: ctypes.WinDLL, handle: int) -> str:
    if not handle:
        return ""
    needed = wintypes.DWORD(0)
    user32.GetUserObjectInformationW(handle, _UOI_NAME, None, 0, ctypes.byref(needed))
    if needed.value == 0:
        return ""
    char_count = max(1, needed.value // ctypes.sizeof(ctypes.c_wchar))
    buf = ctypes.create_unicode_buffer(char_count)
    ok = user32.GetUserObjectInformationW(
        handle,
        _UOI_NAME,
        buf,
        needed.value,
        ctypes.byref(needed),
    )
    if not ok:
        return ""
    return buf.value


def _query_session_locked(wtsapi32: ctypes.WinDLL) -> bool:
    buf_ptr = ctypes.c_void_p()
    bytes_returned = wintypes.DWORD(0)
    ok = wtsapi32.WTSQuerySessionInformationW(
        _WTS_CURRENT_SERVER_HANDLE,
        _WTS_CURRENT_SESSION,
        _WTS_SESSION_INFO_EX,
        ctypes.byref(buf_ptr),
        ctypes.byref(bytes_returned),
    )
    if not ok or not buf_ptr.value:
        return False
    try:
        if bytes_returned.value < ctypes.sizeof(wintypes.DWORD):
            return False
        info = ctypes.cast(buf_ptr, ctypes.POINTER(_WTSINFOEXW)).contents
        if info.Level != 1:
            return False
        return bool(info.Data.SessionFlags == _WTS_SESSIONSTATE_LOCK)
    finally:
        wtsapi32.WTSFreeMemory(buf_ptr.value)


def get_session() -> SessionInfo:
    """Inspect the current Win32 window station, desktops, and session lock state."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    wtsapi32 = ctypes.WinDLL("wtsapi32", use_last_error=True)

    user32.GetProcessWindowStation.argtypes = []
    user32.GetProcessWindowStation.restype = wintypes.HANDLE

    kernel32.GetCurrentThreadId.argtypes = []
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD

    user32.GetThreadDesktop.argtypes = [wintypes.DWORD]
    user32.GetThreadDesktop.restype = wintypes.HANDLE

    user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    user32.OpenInputDesktop.restype = wintypes.HANDLE

    user32.CloseDesktop.argtypes = [wintypes.HANDLE]
    user32.CloseDesktop.restype = wintypes.BOOL

    user32.GetUserObjectInformationW.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetUserObjectInformationW.restype = wintypes.BOOL

    wtsapi32.WTSQuerySessionInformationW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(wintypes.DWORD),
    ]
    wtsapi32.WTSQuerySessionInformationW.restype = wintypes.BOOL

    wtsapi32.WTSFreeMemory.argtypes = [ctypes.c_void_p]
    wtsapi32.WTSFreeMemory.restype = None

    station_handle = int(user32.GetProcessWindowStation() or 0)
    station = _query_object_name(user32, station_handle)

    tid = int(kernel32.GetCurrentThreadId())
    thread_desk_handle = int(user32.GetThreadDesktop(tid) or 0)
    thread_desktop = _query_object_name(user32, thread_desk_handle)

    input_desktop: str | None = None
    input_handle = int(user32.OpenInputDesktop(0, False, _DESKTOP_READOBJECTS) or 0)
    if input_handle:
        try:
            name = _query_object_name(user32, input_handle)
            input_desktop = name or None
        finally:
            user32.CloseDesktop(input_handle)

    locked = _query_session_locked(wtsapi32)
    state = classify_session(station, thread_desktop, input_desktop, locked=locked)
    return SessionInfo(
        station=station,
        thread_desktop=thread_desktop,
        input_desktop=input_desktop,
        state=state,
    )
