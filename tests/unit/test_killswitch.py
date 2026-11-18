"""Unit tests for the global KillSwitch (Win32 event, hotkey thread, failsafe corner)."""

from __future__ import annotations

import time

from edm.actions.killswitch import KillSwitch
from edm.config import Config
from edm.geometry import Point


def test_signal_sets_triggered() -> None:
    """Calling signal() sets triggered() to True and auto-resets after delay."""
    ks = KillSwitch(
        Config(failsafe_corner=False),
        lambda: Point(500, 500),
        reset_delay_s=0.1,
    )
    try:
        assert not ks.triggered()
        ks.signal()
        assert ks.triggered()
        time.sleep(0.25)
        assert not ks.triggered()
    finally:
        ks.stop()


def test_event_shared_across_instances() -> None:
    """Signaling one KillSwitch instance triggers another sharing Local\\EDM_ABORT."""
    cfg = Config(failsafe_corner=False)
    ks1 = KillSwitch(cfg, lambda: Point(500, 500), reset_delay_s=0.5)
    ks2 = KillSwitch(cfg, lambda: Point(500, 500), reset_delay_s=0.5)
    try:
        assert not ks1.triggered()
        assert not ks2.triggered()
        ks1.signal()
        assert ks2.triggered()
    finally:
        ks1.stop()
        ks2.stop()


def test_corner_failsafe() -> None:
    """Cursor within +-1 px of primary_origin triggers failsafe when enabled."""
    pos = Point(0, 0)
    ks = KillSwitch(Config(failsafe_corner=True), lambda: pos, Point(0, 0))
    try:
        assert ks.triggered()
        pos = Point(1, 1)
        assert ks.triggered()
        pos = Point(5, 5)
        assert not ks.triggered()
    finally:
        ks.stop()


def test_corner_disabled_by_config() -> None:
    """Cursor at primary_origin does not trigger when failsafe_corner is False."""
    ks = KillSwitch(Config(failsafe_corner=False), lambda: Point(0, 0), Point(0, 0))
    try:
        assert not ks.triggered()
    finally:
        ks.stop()


def test_stop_cleanup_and_hotkey_thread() -> None:
    """stop() cleans up timer, hotkey thread, and event handle idempotently."""
    ks = KillSwitch(Config(failsafe_corner=False), lambda: Point(500, 500), reset_delay_s=5.0)
    try:
        started = ks.start_hotkey_thread()
        assert isinstance(started, bool)
        ks.signal()
        assert ks.triggered()
    finally:
        ks.stop()
    # Second stop() must be a safe no-op, and triggered() must remain False.
    ks.stop()
    assert not ks.triggered()
