"""Unit tests for Guard preflight checks and inter-agent input lock."""

from __future__ import annotations

import threading
from dataclasses import dataclass

import pytest

from edm.actions.guard import Guard
from edm.config import Config
from edm.errors import EdmError, ErrorCode
from edm.geometry import Point
from edm.win32.process import Integrity
from edm.win32.session import SessionInfo, SessionState


@dataclass
class _StubKillSwitch:
    is_triggered: bool = False

    def triggered(self) -> bool:
        return self.is_triggered


def _session(state: SessionState) -> SessionInfo:
    if state == "isolated_desktop":
        return SessionInfo(
            station="WinSta0",
            thread_desktop="exebox-1",
            input_desktop="Default",
            state=state,
        )
    if state == "secure_desktop":
        return SessionInfo(
            station="WinSta0",
            thread_desktop="Default",
            input_desktop="Winlogon",
            state=state,
        )
    if state == "session_locked":
        return SessionInfo(
            station="WinSta0",
            thread_desktop="Default",
            input_desktop="Default",
            state=state,
        )
    return SessionInfo(
        station="WinSta0",
        thread_desktop="Default",
        input_desktop="Default",
        state="ok",
    )


def _make_guard(
    *,
    session_state: SessionState = "ok",
    aborted: bool = False,
    target_integrity: Integrity = Integrity.medium,
    self_integrity: Integrity = Integrity.medium,
) -> Guard:
    return Guard(
        cfg=Config(),
        session_provider=lambda: _session(session_state),
        killswitch=_StubKillSwitch(is_triggered=aborted),
        integrity_at=lambda _pt: target_integrity,
        self_integrity=self_integrity,
    )


def test_preflight_ok() -> None:
    guard = _make_guard()
    guard.preflight(None)
    guard.preflight(Point(100, 100))


def test_preflight_isolated() -> None:
    guard = _make_guard(session_state="isolated_desktop")
    with pytest.raises(EdmError) as exc:
        guard.preflight(Point(10, 10))
    assert exc.value.code is ErrorCode.ISOLATED_DESKTOP


def test_preflight_secure_desktop() -> None:
    guard = _make_guard(session_state="secure_desktop")
    with pytest.raises(EdmError) as exc:
        guard.preflight(Point(10, 10))
    assert exc.value.code is ErrorCode.SECURE_DESKTOP


def test_preflight_session_locked() -> None:
    guard = _make_guard(session_state="session_locked")
    with pytest.raises(EdmError) as exc:
        guard.preflight(Point(10, 10))
    assert exc.value.code is ErrorCode.SESSION_LOCKED


def test_preflight_elevation_required() -> None:
    guard = _make_guard(
        target_integrity=Integrity.high,
        self_integrity=Integrity.medium,
    )
    with pytest.raises(EdmError) as exc:
        guard.preflight(Point(50, 50))
    assert exc.value.code is ErrorCode.ELEVATION_REQUIRED


def test_preflight_unknown_integrity_assumed_elevated() -> None:
    guard = _make_guard(
        target_integrity=Integrity.unknown,
        self_integrity=Integrity.medium,
    )
    with pytest.raises(EdmError) as exc:
        guard.preflight(Point(50, 50))
    assert exc.value.code is ErrorCode.ELEVATION_REQUIRED
    assert "muhtemelen" in exc.value.message.lower()


def test_preflight_aborted() -> None:
    guard = _make_guard(aborted=True)
    with pytest.raises(EdmError) as exc:
        guard.preflight(Point(10, 10))
    assert exc.value.code is ErrorCode.ABORTED_BY_USER


def test_input_lock_busy() -> None:
    guard_holder = _make_guard()
    guard_waiter = _make_guard()
    acquired = threading.Event()
    release = threading.Event()
    holder_errors: list[BaseException] = []

    def _hold() -> None:
        try:
            with guard_holder.input_lock(timeout_s=2.0):
                acquired.set()
                release.wait(timeout=5.0)
        except BaseException as exc:  # pragma: no cover - diagnostic fallback
            holder_errors.append(exc)
            acquired.set()

    thread = threading.Thread(target=_hold, daemon=True)
    thread.start()
    try:
        assert acquired.wait(timeout=2.0), "Background thread failed to acquire input lock"
        assert not holder_errors, f"Holder thread raised: {holder_errors!r}"
        with pytest.raises(EdmError) as exc, guard_waiter.input_lock(timeout_s=0.2):
            pass
        assert exc.value.code is ErrorCode.BUSY
    finally:
        release.set()
        thread.join(timeout=2.0)
