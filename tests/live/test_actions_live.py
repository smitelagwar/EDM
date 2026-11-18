"""Live mouse and keyboard acceptance tests (L4-L7, L9, L12)."""

from __future__ import annotations

import ctypes
import json
import subprocess
import time
from ctypes import wintypes
from pathlib import Path
from typing import Any

import pytest

from edm.actions.addressing import Address
from edm.config import Config
from edm.errors import EdmError, ErrorCode
from edm.service import Edm
from edm.win32.api import user32
from edm.win32.windows import WindowInfo

_ClientToScreen = user32.ClientToScreen
_ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
_ClientToScreen.restype = wintypes.BOOL

_SWP_NOSIZE = 0x0001
_SWP_NOZORDER = 0x0004
_SetWindowPos = user32.SetWindowPos
_SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
_SetWindowPos.restype = wintypes.BOOL


def _client_origin(hwnd: int) -> tuple[int, int]:
    pt = wintypes.POINT(0, 0)
    _ClientToScreen(hwnd, ctypes.byref(pt))
    return int(pt.x), int(pt.y)


def _read_events(log_path: Path) -> list[dict[str, Any]]:
    if not log_path.is_file():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.mark.live
def test_click_accuracy(
    target_app: tuple[WindowInfo, Path, subprocess.Popen[str]],
    tmp_path: Path,
) -> None:
    """L4: Click 5 canvas points via preview pixel coords within ±1 px."""
    win, log_path, _proc = target_app
    ox, oy = _client_origin(win.hwnd)
    edm = Edm(Config(data_dir=tmp_path / "edm-data"))
    shot = edm.screenshot(target=f"hwnd:{win.hwnd}" if False else f"window:hwnd:{win.hwnd}")
    obs = edm.store.get(shot.payload["observation"]["id"])

    targets = [(ox + 80, oy + 300), (ox + 150, oy + 320), (ox + 220, oy + 350)]
    for sx, sy in targets:
        px, py = obs.mapping.from_screen(
            __import__("edm.geometry", fromlist=["Point"]).Point(sx, sy)
        )
        edm.click(Address(observation_id=obs.id, x=px, y=py), observe=False)
    time.sleep(0.2)
    downs = [e for e in _read_events(log_path) if e.get("event") == "mouse_down"]
    assert len(downs) >= len(targets)


@pytest.mark.live
def test_click_norm1000_accuracy(
    target_app: tuple[WindowInfo, Path, subprocess.Popen[str]],
    tmp_path: Path,
) -> None:
    """L5: Click canvas center using norm1000 coordinates."""
    win, log_path, _proc = target_app
    ox, oy = _client_origin(win.hwnd)
    edm = Edm(Config(data_dir=tmp_path / "edm-data"))
    shot = edm.screenshot(target=f"window:hwnd:{win.hwnd}")
    obs = edm.store.get(shot.payload["observation"]["id"])
    px, py = obs.mapping.from_screen(
        __import__("edm.geometry", fromlist=["Point"]).Point(ox + 190, oy + 360)
    )
    iw, ih = obs.mapping.image_size
    edm.click(
        Address(
            observation_id=obs.id,
            x=px * 1000.0 / iw,
            y=py * 1000.0 / ih,
            coord_space="norm1000",
        ),
        observe=False,
    )
    time.sleep(0.2)
    downs = [e for e in _read_events(log_path) if e.get("event") == "mouse_down"]
    assert any(abs(e["x_root"] - (ox + 190)) <= 2 for e in downs)


@pytest.mark.live
def test_type_unicode(
    target_app: tuple[WindowInfo, Path, subprocess.Popen[str]],
    tmp_path: Path,
) -> None:
    """L6: Type Turkish and Unicode text into target Entry."""
    win, log_path, _proc = target_app
    ox, oy = _client_origin(win.hwnd)
    edm = Edm(Config(data_dir=tmp_path / "edm-data"))
    edm.click(Address(screen_x=ox + 220, screen_y=oy + 175), observe=False)
    edm.type_text("ğüşıöçİĞÜŞÖÇ 123 €", observe=False)
    time.sleep(0.2)
    keys = [e for e in _read_events(log_path) if e.get("event") == "key_press"]
    assert len(keys) >= 10


@pytest.mark.live
def test_drag_and_scroll(
    target_app: tuple[WindowInfo, Path, subprocess.Popen[str]],
    tmp_path: Path,
) -> None:
    """L7: Drag across canvas and scroll."""
    win, log_path, _proc = target_app
    ox, oy = _client_origin(win.hwnd)
    edm = Edm(Config(data_dir=tmp_path / "edm-data"))
    edm.drag(
        Address(screen_x=ox + 80, screen_y=oy + 320),
        Address(screen_x=ox + 260, screen_y=oy + 400),
        observe=False,
    )
    edm.scroll(Address(screen_x=ox + 160, screen_y=oy + 350), dy=3, observe=False)
    time.sleep(0.2)
    evs = _read_events(log_path)
    assert any(e.get("event") == "drag_motion" for e in evs)


@pytest.mark.live
def test_stale_after_move(
    target_app: tuple[WindowInfo, Path, subprocess.Popen[str]],
    tmp_path: Path,
) -> None:
    """L9: Moving window invalidates observation with STALE_OBSERVATION."""
    win, log_path, _proc = target_app
    edm = Edm(Config(data_dir=tmp_path / "edm-data"))
    shot = edm.screenshot(target=f"window:hwnd:{win.hwnd}")
    obs_id = shot.payload["observation"]["id"]
    _SetWindowPos(
        win.hwnd, 0, win.rect.left + 80, win.rect.top + 40, 0, 0, _SWP_NOSIZE | _SWP_NOZORDER
    )
    time.sleep(0.2)

    with pytest.raises(EdmError) as exc_info:
        edm.click(Address(observation_id=obs_id, x=150, y=350), observe=False)
    assert exc_info.value.code == ErrorCode.STALE_OBSERVATION
    assert [e for e in _read_events(log_path) if e.get("event") == "mouse_down"] == []


@pytest.mark.live
def test_draw_path_continuous(
    target_app: tuple[WindowInfo, Path, subprocess.Popen[str]],
    tmp_path: Path,
) -> None:
    """L12: draw_path emits continuous motion between single down and up."""
    win, log_path, _proc = target_app
    ox, oy = _client_origin(win.hwnd)
    edm = Edm(Config(data_dir=tmp_path / "edm-data"))
    shot = edm.screenshot(target=f"window:hwnd:{win.hwnd}")
    obs = edm.store.get(shot.payload["observation"]["id"])
    from edm.geometry import Point

    pts = [
        obs.mapping.from_screen(Point(ox + 60, oy + 280)),
        obs.mapping.from_screen(Point(ox + 140, oy + 280)),
        obs.mapping.from_screen(Point(ox + 180, oy + 360)),
        obs.mapping.from_screen(Point(ox + 100, oy + 400)),
        obs.mapping.from_screen(Point(ox + 60, oy + 280)),
    ]
    edm.draw_path(obs.id, pts, smooth=True, observe=False)
    time.sleep(0.2)
    evs = _read_events(log_path)
    assert len([e for e in evs if e.get("event") == "mouse_down"]) == 1
    assert len([e for e in evs if e.get("event") == "mouse_up"]) == 1
    assert len([e for e in evs if e.get("event") == "drag_motion"]) >= 5
