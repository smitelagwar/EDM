"""Live Windows OCR acceptance test (L8)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from edm.capture.gdi import GdiBackend
from edm.geometry import Rect
from edm.perception.ocr import match_text, ocr_image
from edm.win32.windows import WindowInfo


@pytest.mark.live
def test_find_text_turkish(
    require_interactive: None,
    target_app: tuple[WindowInfo, Path, subprocess.Popen[str]],
) -> None:
    """L8: Capture EDM Target window and find Turkish label text via Windows OCR."""
    del require_interactive
    win, _log_path, _proc = target_app
    frame = GdiBackend().capture_rect(
        Rect(win.rect.left, win.rect.top, win.rect.right, win.rect.bottom)
    )
    lines = ocr_image(frame.image)
    matches = match_text(lines, "iğne şüphe", match="contains")
    assert len(matches) >= 1
    assert matches[0].rect_image.width > 0
    assert matches[0].rect_image.height > 0
