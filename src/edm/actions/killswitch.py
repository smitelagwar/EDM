"""Global emergency kill switch via Win32 event, hotkey thread, and failsafe corner."""

from __future__ import annotations

import ctypes
import threading
from collections.abc import Callable
from ctypes import wintypes

from edm.config import Config
from edm.geometry import Point
from edm.win32.api import CloseHandle, kernel32, user32

_MOD_ALT = 0x0001
_MOD_CONTROL = 0x0002
_MOD_SHIFT = 0x0004
_MOD_NOREPEAT = 0x4000
_VK_F12 = 0x7B

_WM_HOTKEY = 0x0312
_WM_QUIT = 0x0012
_WAIT_OBJECT_0 = 0x00000000

_HOTKEY_ID = 1
_EVENT_NAME = "Local\\EDM_ABORT"
_DEFAULT_RESET_DELAY_S = 2.0
_DEFAULT_ORIGIN = Point(0, 0)

_CreateEventW = kernel32.CreateEventW
_CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
_CreateEventW.restype = wintypes.HANDLE

_SetEvent = kernel32.SetEvent
_SetEvent.argtypes = [wintypes.HANDLE]
_SetEvent.restype = wintypes.BOOL

_ResetEvent = kernel32.ResetEvent
_ResetEvent.argtypes = [wintypes.HANDLE]
_ResetEvent.restype = wintypes.BOOL

_WaitForSingleObject = kernel32.WaitForSingleObject
_WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_WaitForSingleObject.restype = wintypes.DWORD

_GetCurrentThreadId = kernel32.GetCurrentThreadId
_GetCurrentThreadId.argtypes = []
_GetCurrentThreadId.restype = wintypes.DWORD

_RegisterHotKey = user32.RegisterHotKey
_RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
_RegisterHotKey.restype = wintypes.BOOL

_UnregisterHotKey = user32.UnregisterHotKey
_UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
_UnregisterHotKey.restype = wintypes.BOOL

_GetMessageW = user32.GetMessageW
_GetMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
]
_GetMessageW.restype = wintypes.BOOL

_PostThreadMessageW = user32.PostThreadMessageW
_PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_PostThreadMessageW.restype = wintypes.BOOL


class KillSwitch:
    """Monitors Ctrl+Alt+Shift+F12, Local\\EDM_ABORT event, and primary corner failsafe."""

    def __init__(
        self,
        cfg: Config,
        cursor_provider: Callable[[], Point],
        primary_origin: Point = _DEFAULT_ORIGIN,
        *,
        reset_delay_s: float = _DEFAULT_RESET_DELAY_S,
    ) -> None:
        self._cfg = cfg
        self._cursor_provider = cursor_provider
        self._primary_origin = primary_origin
        self._reset_delay_s = reset_delay_s

        self._lock = threading.Lock()
        self._reset_timer: threading.Timer | None = None
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None

        handle = _CreateEventW(None, True, False, _EVENT_NAME)
        if not handle:
            raise OSError(ctypes.get_last_error(), "CreateEventW failed for Local\\EDM_ABORT")
        self._event: wintypes.HANDLE | None = handle

    def start_hotkey_thread(self) -> bool:
        """Start daemon thread listening for Ctrl+Alt+Shift+F12; return False if taken."""
        if self._thread is not None and self._thread.is_alive():
            return True

        ready = threading.Event()
        registered = False

        def _hotkey_loop() -> None:
            nonlocal registered
            self._thread_id = int(_GetCurrentThreadId())
            ok = bool(
                _RegisterHotKey(
                    None,
                    _HOTKEY_ID,
                    _MOD_CONTROL | _MOD_ALT | _MOD_SHIFT | _MOD_NOREPEAT,
                    _VK_F12,
                )
            )
            registered = ok
            ready.set()
            if not ok:
                return
            try:
                msg = wintypes.MSG()
                while _GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                    if msg.message == _WM_HOTKEY and msg.wParam == _HOTKEY_ID:
                        self.signal()
            finally:
                _UnregisterHotKey(None, _HOTKEY_ID)

        thread = threading.Thread(
            target=_hotkey_loop,
            name="edm-killswitch-hotkey",
            daemon=True,
        )
        self._thread = thread
        thread.start()
        ready.wait(timeout=2.0)

        if not registered:
            thread.join(timeout=0.5)
            self._thread = None
            self._thread_id = None
            return False
        return True

    def signal(self) -> None:
        """Set the shared Local\\EDM_ABORT event and schedule a reset after reset_delay_s."""
        with self._lock:
            if self._event is None:
                return
            if self._reset_timer is not None:
                self._reset_timer.cancel()
            _SetEvent(self._event)
            timer = threading.Timer(self._reset_delay_s, self._reset_event)
            timer.daemon = True
            self._reset_timer = timer
            timer.start()

    def _reset_event(self) -> None:
        with self._lock:
            if self._event is not None:
                _ResetEvent(self._event)
            self._reset_timer = None

    def triggered(self) -> bool:
        """Return True if the abort event is signaled or cursor is in the failsafe corner."""
        with self._lock:
            event_handle = self._event
        if event_handle is not None and _WaitForSingleObject(event_handle, 0) == _WAIT_OBJECT_0:
            return True
        if self._cfg.failsafe_corner:
            pos = self._cursor_provider()
            return (
                abs(pos.x - self._primary_origin.x) <= 1
                and abs(pos.y - self._primary_origin.y) <= 1
            )
        return False

    def stop(self) -> None:
        """Cancel pending reset timer, stop hotkey thread, and close event handle."""
        with self._lock:
            if self._reset_timer is not None:
                self._reset_timer.cancel()
                self._reset_timer = None
            event_handle = self._event
            self._event = None

        thread = self._thread
        tid = self._thread_id
        self._thread = None
        self._thread_id = None
        if thread is not None and thread.is_alive() and tid is not None:
            _PostThreadMessageW(tid, _WM_QUIT, 0, 0)
            thread.join(timeout=1.0)

        if event_handle is not None:
            CloseHandle(event_handle)
