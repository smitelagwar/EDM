"""Shared pytest configuration and fixtures for EDM tests."""

from __future__ import annotations

from collections.abc import Iterator
from ctypes import wintypes
from pathlib import Path

import pytest

from edm.config import Config
from edm.fakes import (
    FakeCaptureBackend,
    FakeInputSink,
    FakeSession,
    fake_cursor_position,
    fake_monitors,
    fake_virtual_screen,
    fake_windows,
)
from edm.service import Edm
from edm.win32.api import kernel32

_EVENT_MODIFY_STATE = 0x0002
_OpenEventW = kernel32.OpenEventW
_OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
_OpenEventW.restype = wintypes.HANDLE

_ResetEvent = kernel32.ResetEvent
_ResetEvent.argtypes = [wintypes.HANDLE]
_ResetEvent.restype = wintypes.BOOL


def _clear_abort_event() -> None:
    handle = _OpenEventW(_EVENT_MODIFY_STATE, False, "Local\\EDM_ABORT")
    if handle:
        try:
            _ResetEvent(handle)
        finally:
            kernel32.CloseHandle(handle)


@pytest.fixture(autouse=True)
def _isolate_abort_event() -> Iterator[None]:
    """Ensure Local\\EDM_ABORT does not leak across tests."""
    _clear_abort_event()
    yield
    _clear_abort_event()


@pytest.fixture
def fake_edm(tmp_path: Path) -> Edm:
    """Provide an Edm instance backed by deterministic fakes."""
    cfg = Config(data_dir=tmp_path / "edm-data")
    return Edm(
        cfg,
        session_provider=FakeSession(state="ok"),
        capture_backends={"gdi": FakeCaptureBackend()},
        input_sink=FakeInputSink(),
        monitors_provider=fake_monitors,
        virtual_screen_provider=fake_virtual_screen,
        windows_provider=fake_windows,
        cursor_provider=fake_cursor_position,
        popup_provider=lambda hwnd: hwnd,
    )
