from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from edm.actions.addressing import Address
from edm.actions.mouse import MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP
from edm.config import Config
from edm.errors import EdmError, ErrorCode
from edm.fakes import (
    FakeCaptureBackend,
    FakeInputSink,
    FakeSession,
    fake_cursor_position,
    fake_monitors,
    fake_virtual_screen,
    fake_windows,
)
from edm.geometry import Rect
from edm.service import Edm


def test_click_maps_and_sends(fake_edm: Edm) -> None:
    shot = fake_edm.screenshot(target="screen")
    obs_id = shot.payload["observation"]["id"]

    res = fake_edm.click(Address(observation_id=obs_id, x=156.25, y=156.25))
    assert res.payload["ok"] is True
    assert res.payload["action"] == "click"
    sink = fake_edm.input_sink
    assert isinstance(sink, FakeInputSink)
    assert sink.cursor_pos().x == 250
    assert sink.cursor_pos().y == 250
    mouse_flags = [ev["flags"] for ev in sink.events if ev.get("type") == "mouse"]
    assert mouse_flags == [MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP]


def test_click_norm1000(fake_edm: Edm) -> None:
    shot = fake_edm.screenshot(target="screen")
    obs_id = shot.payload["observation"]["id"]

    res = fake_edm.click(Address(observation_id=obs_id, x=500, y=500, coord_space="norm1000"))
    assert res.payload["ok"] is True
    assert fake_edm.input_sink.cursor_pos().x == 1280
    assert fake_edm.input_sink.cursor_pos().y == 720


def test_click_rejects_moved_window(tmp_path: Path) -> None:
    wins = fake_windows()
    moved = False

    def _win_provider() -> list:
        w = wins[0]
        if not moved:
            return [w]
        from dataclasses import replace

        return [replace(w, rect=Rect(300, 300, 1100, 900))]

    edm = Edm(
        Config(data_dir=tmp_path / "edm-data"),
        session_provider=FakeSession(state="ok"),
        capture_backends={"gdi": FakeCaptureBackend()},
        input_sink=FakeInputSink(),
        monitors_provider=fake_monitors,
        virtual_screen_provider=fake_virtual_screen,
        windows_provider=_win_provider,
        cursor_provider=fake_cursor_position,
        popup_provider=lambda hwnd: hwnd,
    )
    shot = edm.screenshot(target="window:exe:fake.exe")
    obs_id = shot.payload["observation"]["id"]

    moved = True
    with pytest.raises(EdmError) as exc_info:
        edm.click(Address(observation_id=obs_id, x=100, y=100))
    assert exc_info.value.code == ErrorCode.STALE_OBSERVATION
    assert edm.input_sink.events == []


def test_click_rejects_patch_change(tmp_path: Path) -> None:
    paint_white = False

    class _MutatingCapture(FakeCaptureBackend):
        def full_image(self) -> Image.Image:
            img = super().full_image()
            if paint_white:
                img.paste((255, 255, 255), (200, 200, 300, 300))
            return img

    edm = Edm(
        Config(data_dir=tmp_path / "edm-data"),
        session_provider=FakeSession(state="ok"),
        capture_backends={"gdi": _MutatingCapture()},
        input_sink=FakeInputSink(),
        monitors_provider=fake_monitors,
        virtual_screen_provider=fake_virtual_screen,
        windows_provider=fake_windows,
        cursor_provider=fake_cursor_position,
        popup_provider=lambda hwnd: hwnd,
    )
    shot = edm.screenshot(target="screen")
    obs_id = shot.payload["observation"]["id"]

    paint_white = True
    with pytest.raises(EdmError) as exc_info:
        edm.click(Address(observation_id=obs_id, x=156.25, y=156.25))
    assert exc_info.value.code == ErrorCode.STALE_OBSERVATION
    assert edm.input_sink.events == []


def test_click_expired_observation(tmp_path: Path) -> None:
    now = 1_000_000.0
    edm = Edm(
        Config(data_dir=tmp_path / "edm-data"),
        session_provider=FakeSession(state="ok"),
        capture_backends={"gdi": FakeCaptureBackend()},
        input_sink=FakeInputSink(),
        clock=lambda: now,
        monitors_provider=fake_monitors,
        virtual_screen_provider=fake_virtual_screen,
        windows_provider=fake_windows,
        cursor_provider=fake_cursor_position,
        popup_provider=lambda hwnd: hwnd,
    )
    shot = edm.screenshot(target="screen")
    obs_id = shot.payload["observation"]["id"]

    now += 121.0
    with pytest.raises(EdmError) as exc_info:
        edm.click(Address(observation_id=obs_id, x=156.25, y=156.25))
    assert exc_info.value.code == ErrorCode.STALE_OBSERVATION


def test_action_returns_new_observation(fake_edm: Edm) -> None:
    shot = fake_edm.screenshot(target="screen")
    obs_id = shot.payload["observation"]["id"]

    res = fake_edm.click(Address(observation_id=obs_id, x=156.25, y=156.25), observe=True)
    assert "observation" in res.payload
    assert res.payload["observation"]["id"] != obs_id
    assert res.image is not None


def test_actions_logged_jsonl(fake_edm: Edm) -> None:
    shot = fake_edm.screenshot(target="screen")
    obs_id = shot.payload["observation"]["id"]
    fake_edm.click(Address(observation_id=obs_id, x=156.25, y=156.25))

    log_files = list((fake_edm.cfg.data_dir / "logs").glob("actions-*.jsonl"))
    assert len(log_files) == 1
    lines = log_files[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1
    rec = json.loads(lines[-1])
    assert rec["action"] == "click"


def test_draw_path_continuous_and_releases_on_abort(fake_edm: Edm) -> None:
    shot = fake_edm.screenshot(target="screen")
    obs_id = shot.payload["observation"]["id"]

    res = fake_edm.draw_path(
        obs_id,
        [(100, 100), (200, 100), (200, 200)],
        press_button=True,
        smooth=False,
    )
    assert res.payload["ok"] is True
    assert fake_edm.input_sink.held_buttons == set()

    # Now abort mid-path by triggering killswitch when move_to reaches 2nd step
    orig_move = fake_edm.input_sink.move_to
    moves = 0

    def _aborting_move(p):  # type: ignore[no-untyped-def]
        nonlocal moves
        orig_move(p)
        moves += 1
        if moves == 2:
            fake_edm.killswitch.signal()

    fake_edm.input_sink.move_to = _aborting_move  # type: ignore[method-assign]
    with pytest.raises(EdmError) as exc_info:
        fake_edm.draw_path(obs_id, [(100, 100), (200, 100), (200, 200)])
    assert exc_info.value.code == ErrorCode.ABORTED_BY_USER
    assert fake_edm.input_sink.held_buttons == set()


def test_mouse_button_and_key_state_hold_release(fake_edm: Edm) -> None:
    fake_edm.mouse_button("down", button="left", observe=False)
    assert "left" in fake_edm.input_sink.held_buttons
    fake_edm.mouse_button("up", button="left", observe=False)
    assert "left" not in fake_edm.input_sink.held_buttons

    fake_edm.key_state("ctrl", "down", observe=False)
    assert 0x11 in fake_edm.input_sink.held_vks
    fake_edm.key_state("ctrl", "up", observe=False)
    assert 0x11 not in fake_edm.input_sink.held_vks
