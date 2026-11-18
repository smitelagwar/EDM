"""Live interactive desktop test for `edm snip` overlay (L11)."""

from __future__ import annotations

import json
import subprocess
import sys
import time

import pytest

from edm.actions.addressing import Address
from edm.service import Edm


@pytest.mark.live
def test_snip_driven_by_edm(require_interactive: None) -> None:
    """L11: Launch `edm snip`, drive a drag with EDM, and verify captured frame_rect."""
    del require_interactive
    proc = subprocess.Popen(
        [sys.executable, "-m", "edm", "snip", "--prompt", "L11 test snip"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        # Give the borderless Tk overlay a moment to capture and appear.
        time.sleep(1.0)
        edm = Edm.build_default()
        edm.drag(
            Address(screen_x=500, screen_y=300),
            Address(screen_x=900, screen_y=600),
        )
        stdout, stderr = proc.communicate(timeout=15)
        assert proc.returncode == 0, f"edm snip failed: {stderr}"
        payload = json.loads(stdout)
        assert payload["ok"] is True
        obs = payload["observation"]
        left, top, right, bottom = obs["frame_rect"]
        assert abs(left - 500) <= 2
        assert abs(top - 300) <= 2
        assert abs(right - 900) <= 2
        assert abs(bottom - 600) <= 2
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
