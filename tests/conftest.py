"""Shared pytest configuration and fixtures for EDM tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from edm.config import Config
from edm.fakes import FakeCaptureBackend, FakeInputSink, FakeSession
from edm.service import Edm


@pytest.fixture
def fake_edm(tmp_path: Path) -> Edm:
    """Provide an Edm instance backed by deterministic fakes."""
    cfg = Config(data_dir=tmp_path / "edm-data")
    return Edm(
        cfg,
        session_provider=FakeSession(state="ok"),
        capture_backends={"fake": FakeCaptureBackend()},
        input_sink=FakeInputSink(),
    )
