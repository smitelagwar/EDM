"""Shared fixtures for live interactive desktop tests."""

from __future__ import annotations

import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from edm.errors import EdmError
from edm.win32.session import get_session
from edm.win32.windows import WindowInfo, resolve_window


@pytest.fixture
def require_interactive() -> None:
    """Skip live tests cleanly when not running on an interactive desktop."""
    info = get_session()
    if info.state != "ok":
        pytest.skip(f"LIVE-PENDING: {info.state}")


@pytest.fixture
def target_app(
    require_interactive: None,
    tmp_path: Path,
) -> Iterator[tuple[WindowInfo, Path, subprocess.Popen[str]]]:
    """Launch ``target_app.py`` and wait up to 10 s for its window."""
    del require_interactive
    log_path = tmp_path / "target_events.jsonl"
    script = Path(__file__).with_name("target_app.py")
    proc = subprocess.Popen(
        [sys.executable, str(script), "--log", str(log_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 10.0
        win: WindowInfo | None = None
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f"target_app exited early with {proc.returncode}")
            try:
                win, _ = resolve_window("title:EDM Target")
                break
            except EdmError:
                time.sleep(0.1)
        if win is None:
            raise TimeoutError("Timed out waiting for 'EDM Target' window")
        yield win, log_path, proc
    finally:
        proc.kill()
        proc.wait(timeout=5)
