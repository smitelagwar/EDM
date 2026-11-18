"""Environment diagnostics report for ``edm doctor``."""

from __future__ import annotations

import importlib.util
import platform
from typing import TYPE_CHECKING, Any

from edm import __version__
from edm.errors import NEXT_STEP, ErrorCode
from edm.win32.monitors import list_monitors, virtual_screen
from edm.win32.process import Integrity, integrity_rank, self_integrity

if TYPE_CHECKING:
    from edm.service import Edm


def _has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ModuleNotFoundError, ValueError):
        return False


def _ocr_status() -> dict[str, Any]:
    if not _has_module("winrt.windows.media.ocr"):
        return {"available": False, "languages": []}
    try:
        from winrt.windows.media.ocr import OcrEngine  # type: ignore[import-not-found]

        langs = [str(lang.language_tag) for lang in OcrEngine.available_recognizer_languages]
        return {"available": True, "languages": langs}
    except Exception:
        return {"available": False, "languages": []}


def run_doctor(edm: Edm) -> dict[str, Any]:
    """Collect a structured diagnostic report for the current EDM environment."""
    session = edm.session_provider()
    integrity = self_integrity()
    elevated = integrity_rank(integrity) >= integrity_rank(Integrity.high)
    monitors = [
        {
            "index": m.index,
            "device": m.device,
            "rect": m.rect.as_list(),
            "work_rect": m.work_rect.as_list(),
            "dpi": m.dpi,
            "scale": m.scale,
            "primary": m.primary,
        }
        for m in list_monitors()
    ]

    hints: list[str] = []
    if session.state == "isolated_desktop":
        hints.append(NEXT_STEP[ErrorCode.ISOLATED_DESKTOP])
    elif session.state == "secure_desktop":
        hints.append(NEXT_STEP[ErrorCode.SECURE_DESKTOP])
    elif session.state == "session_locked":
        hints.append(NEXT_STEP[ErrorCode.SESSION_LOCKED])

    return {
        "version": __version__,
        "python": platform.python_version(),
        "os_build": platform.version(),
        "session": {
            "station": session.station,
            "thread_desktop": session.thread_desktop,
            "input_desktop": session.input_desktop,
            "state": session.state,
        },
        "elevated": elevated,
        "integrity": str(integrity),
        "dpi_awareness": edm.dpi_awareness,
        "monitors": monitors,
        "virtual_screen": virtual_screen().as_list(),
        "backends": {
            "gdi": _has_module("mss"),
            "wgc": _has_module("windows_capture"),
            "printwindow": True,
            "uia": _has_module("uiautomation") and _has_module("comtypes"),
            "ocr": _ocr_status(),
        },
        "killswitch": {
            "hotkey": edm.cfg.killswitch_hotkey,
            "failsafe_corner": edm.cfg.failsafe_corner,
        },
        "data_dir": str(edm.cfg.data_dir),
        "hints": hints,
    }
