"""Live UI Automation acceptance tests (L2b)."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest

from edm.actions.addressing import Address
from edm.config import Config
from edm.perception.uia import collect_elements
from edm.service import Edm
from edm.win32.windows import WindowInfo


@pytest.mark.live
def test_uia_button_click(
    target_app: tuple[WindowInfo, Path, subprocess.Popen[str]],
    tmp_path: Path,
) -> None:
    """L2b: Locate EDM-OK button via UIA and click its center."""
    win, log_path, _proc = target_app
    elements, _truncated = collect_elements(win.hwnd)
    ok_btns = [e for e in elements if e.control_type == "Button" and e.name == "EDM-OK"]
    assert len(ok_btns) == 1

    center = ok_btns[0].rect.center
    edm = Edm(Config(data_dir=tmp_path / "edm-data"))
    edm.click(Address(screen_x=center.x, screen_y=center.y), observe=False)
    time.sleep(0.2)
    lines = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(e.get("event") == "button_click" and e.get("name") == "EDM-OK" for e in lines)
