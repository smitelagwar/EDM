"""Unit tests for Win32 session and desktop classification."""

from __future__ import annotations

import ctypes
from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from edm.win32.session import (
    _WTSINFOEXW,
    SessionInfo,
    SessionState,
    classify_session,
    get_session,
)


@pytest.mark.parametrize(
    ("station", "thread_desktop", "input_desktop", "locked", "expected"),
    [
        ("WinSta0", "Default", "Default", False, "ok"),
        ("WinSta0", "exebox-ABC", "Default", False, "isolated_desktop"),
        ("WinSta0", "Default", "Winlogon", False, "secure_desktop"),
        ("WinSta0", "Default", None, False, "secure_desktop"),
        ("WinSta0", "Default", "Default", True, "session_locked"),
        ("Service-0x0-3e7$", "Default", None, False, "isolated_desktop"),
    ],
)
def test_classify_session_table(
    station: str,
    thread_desktop: str,
    input_desktop: str | None,
    locked: bool,
    expected: SessionState,
) -> None:
    """classify_session matches the T1.2 truth table."""
    assert classify_session(station, thread_desktop, input_desktop, locked) == expected


def test_session_info_frozen() -> None:
    """SessionInfo is a frozen dataclass with expected fields."""
    info = SessionInfo(
        station="WinSta0",
        thread_desktop="Default",
        input_desktop="Default",
        state="ok",
    )
    assert info.station == "WinSta0"
    assert info.thread_desktop == "Default"
    assert info.input_desktop == "Default"
    assert info.state == "ok"
    with pytest.raises(FrozenInstanceError):
        info.state = "secure_desktop"  # type: ignore[misc]


def test_get_session_live_shape() -> None:
    """get_session queries Win32 and returns a well-formed SessionInfo."""
    info = get_session()
    assert isinstance(info, SessionInfo)
    assert isinstance(info.station, str) and info.station != ""
    assert isinstance(info.thread_desktop, str) and info.thread_desktop != ""
    assert info.input_desktop is None or isinstance(info.input_desktop, str)
    assert info.state in {"ok", "isolated_desktop", "secure_desktop", "session_locked"}


class _FakeFn:
    def __init__(self, impl: Any) -> None:
        self._impl = impl
        self.argtypes: Any = None
        self.restype: Any = None

    def __call__(self, *args: Any) -> Any:
        return self._impl(*args)


class _FakeDLL:
    def __init__(self, funcs: dict[str, Any]) -> None:
        self._funcs = {k: _FakeFn(v) for k, v in funcs.items()}

    def __getattr__(self, name: str) -> _FakeFn:
        return self._funcs[name]


@pytest.mark.parametrize(
    ("station", "thread_desk", "input_desk", "wts_ok", "session_flags", "expected_state"),
    [
        ("WinSta0", "Default", "Default", True, 1, "ok"),
        ("WinSta0", "exebox-ABC", "Default", True, 1, "isolated_desktop"),
        ("WinSta0", "Default", None, True, 1, "secure_desktop"),
        ("WinSta0", "Default", "Winlogon", True, 1, "secure_desktop"),
        ("WinSta0", "Default", "Default", True, 0, "session_locked"),
        ("WinSta0", "Default", "Default", False, 0, "ok"),
    ],
)
def test_get_session_mocked_win32(
    monkeypatch: pytest.MonkeyPatch,
    station: str,
    thread_desk: str,
    input_desk: str | None,
    wts_ok: bool,
    session_flags: int,
    expected_state: SessionState,
) -> None:
    """get_session handles desktop names, OpenInputDesktop denial, and WTS lock state."""
    closed_handles: list[int] = []
    freed_ptrs: list[int] = []
    wts_struct = _WTSINFOEXW()
    wts_struct.Level = 1
    wts_struct.Data.SessionFlags = session_flags

    handle_names = {101: station, 102: thread_desk}
    if input_desk is not None:
        handle_names[103] = input_desk

    def get_uoi(
        handle: int,
        index: int,
        buf: Any,
        length: int,
        needed_ptr: Any,
    ) -> int:
        name = handle_names[handle]
        encoded = (name + "\0").encode("utf-16-le")
        needed_ptr._obj.value = len(encoded)
        if buf is None or length < len(encoded):
            return 0
        ctypes.memmove(buf, encoded, len(encoded))
        return 1

    def open_input(_flags: int, _inherit: bool, _access: int) -> int:
        return 103 if input_desk is not None else 0

    def close_desktop(handle: int) -> int:
        closed_handles.append(handle)
        return 1

    def wts_query(
        _server: Any,
        _session_id: int,
        _info_class: int,
        buf_ptr: Any,
        bytes_returned_ptr: Any,
    ) -> int:
        if not wts_ok:
            return 0
        buf_ptr._obj.value = ctypes.addressof(wts_struct)
        bytes_returned_ptr._obj.value = ctypes.sizeof(wts_struct)
        return 1

    def wts_free(ptr: int) -> None:
        freed_ptrs.append(ptr)

    user32 = _FakeDLL(
        {
            "GetProcessWindowStation": lambda: 101,
            "GetThreadDesktop": lambda _tid: 102,
            "OpenInputDesktop": open_input,
            "CloseDesktop": close_desktop,
            "GetUserObjectInformationW": get_uoi,
        }
    )
    kernel32 = _FakeDLL({"GetCurrentThreadId": lambda: 4242})
    wtsapi32 = _FakeDLL(
        {
            "WTSQuerySessionInformationW": wts_query,
            "WTSFreeMemory": wts_free,
        }
    )

    dlls = {"user32": user32, "kernel32": kernel32, "wtsapi32": wtsapi32}
    monkeypatch.setattr(ctypes, "WinDLL", lambda name, use_last_error=True: dlls[name])

    info = get_session()
    assert info == SessionInfo(
        station=station,
        thread_desktop=thread_desk,
        input_desktop=input_desk,
        state=expected_state,
    )
    if input_desk is not None:
        assert closed_handles == [103]
    else:
        assert closed_handles == []
    if wts_ok:
        assert freed_ptrs == [ctypes.addressof(wts_struct)]
    else:
        assert freed_ptrs == []
