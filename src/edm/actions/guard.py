"""Action preflight guard: session state, kill switch, UIPI, and input lock."""

from __future__ import annotations

import ctypes
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from ctypes import wintypes
from typing import Protocol

from edm.config import Config
from edm.errors import EdmError, ErrorCode
from edm.geometry import Point
from edm.win32.api import CloseHandle, kernel32
from edm.win32.process import Integrity, integrity_rank
from edm.win32.session import SessionInfo

_INPUT_LOCK_NAME = "Local\\EDM_INPUT_LOCK"
_WAIT_OBJECT_0 = 0x00000000
_WAIT_ABANDONED = 0x00000080
_WAIT_TIMEOUT = 0x00000102

_CreateMutexW = kernel32.CreateMutexW
_CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
_CreateMutexW.restype = wintypes.HANDLE

_WaitForSingleObject = kernel32.WaitForSingleObject
_WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_WaitForSingleObject.restype = wintypes.DWORD

_ReleaseMutex = kernel32.ReleaseMutex
_ReleaseMutex.argtypes = [wintypes.HANDLE]
_ReleaseMutex.restype = wintypes.BOOL


class KillSwitchLike(Protocol):
    """Protocol for kill-switch implementations checked before input."""

    def triggered(self) -> bool:
        """Return True when the user has triggered an abort."""
        ...


_SESSION_ERROR_MAP: dict[str, tuple[ErrorCode, str]] = {
    "isolated_desktop": (
        ErrorCode.ISOLATED_DESKTOP,
        "Process is running on an isolated desktop rather than WinSta0\\Default.",
    ),
    "secure_desktop": (
        ErrorCode.SECURE_DESKTOP,
        "A UAC or secure desktop prompt is currently active.",
    ),
    "session_locked": (
        ErrorCode.SESSION_LOCKED,
        "The Windows user session is locked.",
    ),
}


class Guard:
    """Enforces session, kill-switch, UIPI integrity, and mutex serialization."""

    def __init__(
        self,
        cfg: Config,
        session_provider: Callable[[], SessionInfo],
        killswitch: KillSwitchLike,
        integrity_at: Callable[[Point], Integrity],
        self_integrity: Integrity,
    ) -> None:
        self._cfg = cfg
        self._session_provider = session_provider
        self._killswitch = killswitch
        self._integrity_at = integrity_at
        self._self_integrity = self_integrity

    def preflight(self, point: Point | None) -> None:
        """Verify desktop session, kill switch, and UIPI integrity before sending input."""
        session = self._session_provider()
        if session.state != "ok":
            code, msg = _SESSION_ERROR_MAP.get(
                session.state,
                (ErrorCode.ISOLATED_DESKTOP, f"Desktop session state is {session.state!r}."),
            )
            raise EdmError(
                code,
                msg,
                details={
                    "state": session.state,
                    "station": session.station,
                    "thread_desktop": session.thread_desktop,
                    "input_desktop": session.input_desktop,
                },
            )

        if self._killswitch.triggered():
            raise EdmError(
                ErrorCode.ABORTED_BY_USER,
                "Action aborted by user kill switch.",
            )

        if point is not None:
            target = self._integrity_at(point)
            if target == Integrity.unknown and integrity_rank(
                self._self_integrity
            ) <= integrity_rank(Integrity.medium):
                raise EdmError(
                    ErrorCode.ELEVATION_REQUIRED,
                    "Hedef pencere bütünlüğü okunamadı; muhtemelen yönetici yetkili (elevated).",
                    details={
                        "target_integrity": str(target),
                        "self_integrity": str(self._self_integrity),
                        "point": [point.x, point.y],
                    },
                )
            if integrity_rank(target) > integrity_rank(self._self_integrity):
                raise EdmError(
                    ErrorCode.ELEVATION_REQUIRED,
                    f"Target integrity ({target}) exceeds EDM integrity ({self._self_integrity}).",
                    details={
                        "target_integrity": str(target),
                        "self_integrity": str(self._self_integrity),
                        "point": [point.x, point.y],
                    },
                )

    @contextmanager
    def input_lock(self, timeout_s: float | None = None) -> Iterator[None]:
        """Acquire the cross-process ``Local\\EDM_INPUT_LOCK`` mutex for the duration."""
        effective_timeout = self._cfg.input_lock_timeout_s if timeout_s is None else timeout_s
        timeout_ms = max(0, int(round(effective_timeout * 1000)))
        handle = _CreateMutexW(None, False, _INPUT_LOCK_NAME)
        if not handle:
            err = ctypes.get_last_error()
            raise EdmError(
                ErrorCode.INTERNAL,
                f"Failed to create input lock mutex (win32 error {err}).",
                details={"win32_error": err},
            )

        acquired = False
        try:
            wait_res = int(_WaitForSingleObject(handle, timeout_ms))
            if wait_res in (_WAIT_OBJECT_0, _WAIT_ABANDONED):
                acquired = True
                yield
            elif wait_res == _WAIT_TIMEOUT:
                raise EdmError(
                    ErrorCode.BUSY,
                    (
                        "Another EDM action holds the input lock "
                        f"(timed out after {effective_timeout}s)."
                    ),
                    details={"timeout_s": effective_timeout},
                )
            else:
                err = ctypes.get_last_error()
                raise EdmError(
                    ErrorCode.INTERNAL,
                    f"WaitForSingleObject failed with status {wait_res} (win32 error {err}).",
                    details={"wait_status": wait_res, "win32_error": err},
                )
        finally:
            if acquired:
                _ReleaseMutex(handle)
            CloseHandle(handle)
