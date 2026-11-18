"""Win32 process executable and integrity level queries."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from enum import StrEnum
from pathlib import Path

from edm.win32.api import advapi32, kernel32

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_TOKEN_QUERY = 0x0008
_TOKEN_INTEGRITY_LEVEL = 25

_SECURITY_MANDATORY_LOW_RID = 0x1000
_SECURITY_MANDATORY_MEDIUM_RID = 0x2000
_SECURITY_MANDATORY_HIGH_RID = 0x3000
_SECURITY_MANDATORY_SYSTEM_RID = 0x4000


class _SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Sid", ctypes.c_void_p),
        ("Attributes", wintypes.DWORD),
    ]


class _TOKEN_MANDATORY_LABEL(ctypes.Structure):
    _fields_ = [("Label", _SID_AND_ATTRIBUTES)]


_OpenProcess = kernel32.OpenProcess
_OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_OpenProcess.restype = wintypes.HANDLE

_QueryFullProcessImageNameW = kernel32.QueryFullProcessImageNameW
_QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
_QueryFullProcessImageNameW.restype = wintypes.BOOL

_OpenProcessToken = advapi32.OpenProcessToken
_OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
_OpenProcessToken.restype = wintypes.BOOL

_GetTokenInformation = advapi32.GetTokenInformation
_GetTokenInformation.argtypes = [
    wintypes.HANDLE,
    ctypes.c_int,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
]
_GetTokenInformation.restype = wintypes.BOOL

_GetSidSubAuthorityCount = advapi32.GetSidSubAuthorityCount
_GetSidSubAuthorityCount.argtypes = [ctypes.c_void_p]
_GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)

_GetSidSubAuthority = advapi32.GetSidSubAuthority
_GetSidSubAuthority.argtypes = [ctypes.c_void_p, wintypes.DWORD]
_GetSidSubAuthority.restype = ctypes.POINTER(wintypes.DWORD)


class Integrity(StrEnum):
    """Windows process mandatory integrity levels."""

    untrusted = "untrusted"
    low = "low"
    medium = "medium"
    high = "high"
    system = "system"
    unknown = "unknown"


_INTEGRITY_RANKS: dict[Integrity, int] = {
    Integrity.unknown: -1,
    Integrity.untrusted: 0,
    Integrity.low: 1,
    Integrity.medium: 2,
    Integrity.high: 3,
    Integrity.system: 4,
}


def integrity_rank(i: Integrity) -> int:
    """Return numeric rank for comparing integrity levels."""
    return _INTEGRITY_RANKS[i]


def _rid_to_integrity(rid: int) -> Integrity:
    if rid < _SECURITY_MANDATORY_LOW_RID:
        return Integrity.untrusted
    if rid < _SECURITY_MANDATORY_MEDIUM_RID:
        return Integrity.low
    if rid < _SECURITY_MANDATORY_HIGH_RID:
        return Integrity.medium
    if rid < _SECURITY_MANDATORY_SYSTEM_RID:
        return Integrity.high
    return Integrity.system


def process_integrity(pid: int) -> Integrity:
    """Return the mandatory integrity level of *pid*, or ``Integrity.unknown``."""
    if pid <= 0:
        return Integrity.unknown
    h_proc = _OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h_proc:
        return Integrity.unknown
    h_token = wintypes.HANDLE()
    try:
        if not _OpenProcessToken(h_proc, _TOKEN_QUERY, ctypes.byref(h_token)):
            return Integrity.unknown
        needed = wintypes.DWORD(0)
        _GetTokenInformation(h_token, _TOKEN_INTEGRITY_LEVEL, None, 0, ctypes.byref(needed))
        if needed.value == 0:
            return Integrity.unknown
        buf = (ctypes.c_ubyte * needed.value)()
        if not _GetTokenInformation(
            h_token,
            _TOKEN_INTEGRITY_LEVEL,
            ctypes.byref(buf),
            needed.value,
            ctypes.byref(needed),
        ):
            return Integrity.unknown
        label = ctypes.cast(ctypes.byref(buf), ctypes.POINTER(_TOKEN_MANDATORY_LABEL)).contents
        sid_ptr = label.Label.Sid
        if not sid_ptr:
            return Integrity.unknown
        count_ptr = _GetSidSubAuthorityCount(sid_ptr)
        if not count_ptr or count_ptr[0] == 0:
            return Integrity.unknown
        rid_ptr = _GetSidSubAuthority(sid_ptr, count_ptr[0] - 1)
        if not rid_ptr:
            return Integrity.unknown
        return _rid_to_integrity(int(rid_ptr[0]))
    finally:
        if h_token:
            kernel32.CloseHandle(h_token)
        kernel32.CloseHandle(h_proc)


def self_integrity() -> Integrity:
    """Return the mandatory integrity level of the current process."""
    return process_integrity(int(kernel32.GetCurrentProcessId()))


def process_exe(pid: int) -> str:
    """Return the executable basename (e.g. ``notepad.exe``) for *pid*, or ``""``."""
    if pid <= 0:
        return ""
    h_proc = _OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h_proc:
        return ""
    try:
        buf_len = 1024
        buf = ctypes.create_unicode_buffer(buf_len)
        size = wintypes.DWORD(buf_len)
        if not _QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size)):
            return ""
        return Path(buf.value).name
    finally:
        kernel32.CloseHandle(h_proc)
