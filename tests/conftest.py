"""Shared pytest configuration and fixtures for EDM tests."""

from __future__ import annotations

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
    )
