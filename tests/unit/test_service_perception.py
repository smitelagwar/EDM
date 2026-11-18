from __future__ import annotations

import json
from pathlib import Path

import pytest

from edm.actions.addressing import Address
from edm.cli import main
from edm.config import Config
from edm.errors import EdmError, ErrorCode
from edm.fakes import (
    FakeCaptureBackend,
    FakeClipboard,
    FakeInputSink,
    FakeOcrEngine,
    FakeSession,
    FakeSnipSelector,
    FakeUiaProvider,
    fake_cursor_position,
    fake_monitors,
    fake_virtual_screen,
    fake_windows,
)
from edm.geometry import Rect
from edm.service import Edm


def test_click_by_mark_resolves_center(fake_edm: Edm) -> None:
    res = fake_edm.ui_elements(window="exe:fake.exe")
    assert res.payload["ok"] is True
    assert res.payload["action"] == "ui_elements"
    elements = res.payload["details"]["elements"]
    assert len(elements) >= 1
    obs_id = res.payload["observation"]["id"]

    # FakeUiaProvider puts mark 1 ("EDM-OK" Button) at Rect(200, 200, 300, 260) -> center (250, 230)
    click_res = fake_edm.click(Address(observation_id=obs_id, mark=1), verify=False, observe=False)
    assert click_res.payload["ok"] is True
    pos = fake_edm.input_sink.cursor_pos()
    assert pos.x == 250
    assert pos.y == 230


def test_find_text_and_address_text(fake_edm: Edm) -> None:
    res = fake_edm.find_text("Şüphe", target="screen", match="contains")
    assert res.payload["ok"] is True
    matches = res.payload["details"]["matches"]
    assert len(matches) >= 1
    assert "rect_screen" in matches[0]
    assert "rect_image" in matches[0]

    # Address(text="Tamam") resolves to center of FakeOcrEngine's "Tamam" box
    click_res = fake_edm.click(Address(text="Tamam"), verify=False, observe=False)
    assert click_res.payload["ok"] is True
    pos = fake_edm.input_sink.cursor_pos()
    assert pos.x == 450
    assert pos.y == 320

    with pytest.raises(EdmError) as exc_info:
        fake_edm.click(Address(text="NoSuchTextOnScreen"), verify=False, observe=False)
    assert exc_info.value.code == ErrorCode.WINDOW_NOT_FOUND


def test_find_text_rect_image_maps_to_screen(fake_edm: Edm) -> None:
    res = fake_edm.find_text("Tamam", target="screen", match="exact")
    obs_id = res.payload["observation"]["id"]
    r_img = res.payload["details"]["matches"][0]["rect_image"]
    cx = (r_img[0] + r_img[2]) / 2.0
    cy = (r_img[1] + r_img[3]) / 2.0

    click_res = fake_edm.click(
        Address(observation_id=obs_id, x=cx, y=cy),
        verify=False,
        observe=False,
    )
    assert click_res.payload["ok"] is True
    pos = fake_edm.input_sink.cursor_pos()
    assert abs(pos.x - 450) <= 1
    assert abs(pos.y - 320) <= 1


def test_screenshot_window_marks_preserves_options(fake_edm: Edm) -> None:
    res = fake_edm.screenshot(
        target="window:exe:fake.exe",
        max_edge=800,
        grid=True,
        marks=True,
    )
    assert res.payload["ok"] is True
    assert res.payload["action"] == "screenshot"
    obs_dict = res.payload["observation"]
    assert max(obs_dict["image_size"]) == 800
    obs = fake_edm.store.get(obs_dict["id"])
    assert len(obs.marks) >= 1


def test_wait_for_text(fake_edm: Edm) -> None:
    res = fake_edm.wait_for("text", query="Tamam", timeout_s=1.0)
    assert res.payload["ok"] is True

    with pytest.raises(EdmError) as exc_info:
        fake_edm.wait_for("text", query="NeverAppearsText", timeout_s=0.1)
    assert exc_info.value.code == ErrorCode.TIMEOUT


def test_request_user_region_and_cancelled(tmp_path: Path) -> None:
    cfg = Config(data_dir=tmp_path / "edm-data")
    edm = Edm(
        cfg,
        session_provider=FakeSession(state="ok"),
        capture_backends={"gdi": FakeCaptureBackend()},
        input_sink=FakeInputSink(),
        monitors_provider=fake_monitors,
        virtual_screen_provider=fake_virtual_screen,
        windows_provider=fake_windows,
        cursor_provider=fake_cursor_position,
        popup_provider=lambda hwnd: hwnd,
        clipboard_backend=FakeClipboard(),
        window_action_fn=lambda _h, _a, _r: None,
        launcher_fn=lambda _s, _a: None,
        uia_provider=FakeUiaProvider(),
        ocr_fn=FakeOcrEngine(),
        snip_fn=FakeSnipSelector(rect=Rect(200, 200, 500, 400)),
    )
    res = edm.request_user_region(prompt="Select area")
    assert res.payload["ok"] is True
    assert res.payload["details"]["cancelled"] is False
    assert res.payload["observation"]["frame_rect"] == [200, 200, 500, 400]

    edm_cancel = Edm(
        cfg,
        session_provider=FakeSession(state="ok"),
        capture_backends={"gdi": FakeCaptureBackend()},
        input_sink=FakeInputSink(),
        monitors_provider=fake_monitors,
        virtual_screen_provider=fake_virtual_screen,
        windows_provider=fake_windows,
        cursor_provider=fake_cursor_position,
        popup_provider=lambda hwnd: hwnd,
        clipboard_backend=FakeClipboard(),
        window_action_fn=lambda _h, _a, _r: None,
        launcher_fn=lambda _s, _a: None,
        uia_provider=FakeUiaProvider(),
        ocr_fn=FakeOcrEngine(),
        snip_fn=FakeSnipSelector(rect=None),
    )
    cancel_res = edm_cancel.request_user_region()
    assert cancel_res.payload["ok"] is True
    assert cancel_res.payload["details"]["cancelled"] is True


def test_get_user_snips_latest_first(tmp_path: Path) -> None:
    now = 1_000_000.0

    def _clock() -> float:
        nonlocal now
        now += 1.0
        return now

    cfg = Config(data_dir=tmp_path / "edm-data")
    rects = iter([Rect(100, 100, 300, 250), Rect(400, 200, 700, 500)])

    edm = Edm(
        cfg,
        session_provider=FakeSession(state="ok"),
        capture_backends={"gdi": FakeCaptureBackend()},
        input_sink=FakeInputSink(),
        clock=_clock,
        monitors_provider=fake_monitors,
        virtual_screen_provider=fake_virtual_screen,
        windows_provider=fake_windows,
        cursor_provider=fake_cursor_position,
        popup_provider=lambda hwnd: hwnd,
        clipboard_backend=FakeClipboard(),
        window_action_fn=lambda _h, _a, _r: None,
        launcher_fn=lambda _s, _a: None,
        uia_provider=FakeUiaProvider(),
        ocr_fn=FakeOcrEngine(),
        snip_fn=lambda _img, _vs, _prompt, _to: next(rects),
    )
    r1 = edm.request_user_region()
    r2 = edm.request_user_region()
    snips = edm.get_user_snips(limit=2)
    assert snips.payload["ok"] is True
    items = snips.payload["snips"]
    assert len(items) == 2
    assert items[0]["id"] == r2.payload["observation"]["id"]
    assert items[1]["id"] == r1.payload["observation"]["id"]


def test_cli_perception_commands(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("EDM_FAKE", "1")
    monkeypatch.setenv("EDM_DATA_DIR", str(tmp_path / "edm-data"))

    assert main(["elements", "--window", "exe:fake.exe"]) == 0
    el_out = json.loads(capsys.readouterr().out)
    assert el_out["ok"] is True

    assert main(["find-text", "Şüphe"]) == 0
    ft_out = json.loads(capsys.readouterr().out)
    assert ft_out["ok"] is True
    assert len(ft_out["details"]["matches"]) >= 1

    assert main(["snip", "--prompt", "Demo"]) == 0
    sn_out = json.loads(capsys.readouterr().out)
    assert sn_out["ok"] is True
    assert sn_out["details"]["cancelled"] is False
