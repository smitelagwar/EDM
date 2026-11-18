from __future__ import annotations

import json
from pathlib import Path

import pytest

from edm.cli import main
from edm.errors import EdmError, ErrorCode
from edm.service import Edm


def test_screenshot_payload(fake_edm: Edm) -> None:
    res = fake_edm.screenshot(target="screen")
    assert res.payload["ok"] is True
    assert res.payload["action"] == "screenshot"
    obs = res.payload["observation"]
    assert obs["image_size"] == [1600, 900]
    assert obs["scale"] == 0.625
    assert obs["frame_rect"] == [0, 0, 2560, 1440]
    assert res.image is not None
    assert len(res.image) > 0
    assert res.mime in {"image/png", "image/jpeg"}
    assert "foreground_window" in res.payload["details"]
    assert (fake_edm.cfg.data_dir / "index.jsonl").is_file()
    assert not (fake_edm.cfg.data_dir / "observations" / "observations").exists()


def test_zoom_maps_back(fake_edm: Edm) -> None:
    shot = fake_edm.screenshot(target="screen")
    obs_id = shot.payload["observation"]["id"]

    # Red square in FakeCaptureBackend is (200,200)-(300,300) in 2560x1440.
    # In 1600x900 (scale=0.625), that is (125,125)-(187.5,187.5).
    zoomed = fake_edm.zoom(obs_id, 125, 125, 63, 63)
    assert zoomed.payload["ok"] is True
    assert zoomed.payload["action"] == "zoom"
    z_obs_dict = zoomed.payload["observation"]
    assert z_obs_dict["parent_id"] == obs_id

    z_obs = fake_edm.store.get(z_obs_dict["id"])
    zw, zh = z_obs.mapping.image_size
    pt = z_obs.mapping.to_screen(zw / 2.0, zh / 2.0)
    assert abs(pt.x - 250) <= 1
    assert abs(pt.y - 250) <= 1


def test_zoom_fresh_links_parent(fake_edm: Edm) -> None:
    shot = fake_edm.screenshot(target="screen")
    obs_id = shot.payload["observation"]["id"]

    zoomed = fake_edm.zoom(obs_id, 125, 125, 63, 63, fresh=True)
    z_obs_dict = zoomed.payload["observation"]
    assert z_obs_dict["parent_id"] == obs_id
    assert zoomed.payload["details"]["fresh"] is True


def test_zoom_out_of_bounds_raises(fake_edm: Edm) -> None:
    shot = fake_edm.screenshot(target="screen")
    obs_id = shot.payload["observation"]["id"]

    with pytest.raises(EdmError) as exc_info:
        fake_edm.zoom(obs_id, 1590, 890, 50, 50)
    assert exc_info.value.code == ErrorCode.POINT_OUT_OF_BOUNDS


def test_zoom_nan_and_norm1000_right_edge(fake_edm: Edm) -> None:
    shot = fake_edm.screenshot(target="screen")
    obs_id = shot.payload["observation"]["id"]

    with pytest.raises(EdmError) as exc_info:
        fake_edm.zoom(obs_id, float("nan"), 0, 10, 10)
    assert exc_info.value.code == ErrorCode.INVALID_ARGUMENT

    edge = fake_edm.zoom(obs_id, 999.9, 999.9, 0.1, 0.1, coord_space="norm1000")
    assert edge.payload["ok"] is True
    assert edge.payload["observation"]["parent_id"] == obs_id


def test_list_windows_fake(fake_edm: Edm) -> None:
    res = fake_edm.list_windows()
    assert res.payload["ok"] is True
    assert len(res.payload["windows"]) >= 1

    filtered = fake_edm.list_windows(query="exe:fake.exe")
    assert len(filtered.payload["windows"]) >= 1
    assert filtered.payload["windows"][0]["exe"] == "fake.exe"


def test_list_monitors_fake(fake_edm: Edm) -> None:
    res = fake_edm.list_monitors()
    assert res.payload["ok"] is True
    mons = res.payload["monitors"]
    assert len(mons) == 1
    assert mons[0]["primary"] is True
    assert mons[0]["rect"] == [0, 0, 2560, 1440]


def test_cli_capture_subcommands(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("EDM_FAKE", "1")
    monkeypatch.setenv("EDM_DATA_DIR", str(tmp_path / "edm-data"))

    assert main(["monitors"]) == 0
    mons_out = json.loads(capsys.readouterr().out)
    assert mons_out["ok"] is True

    assert main(["windows", "--query", "fake.exe"]) == 0
    wins_out = json.loads(capsys.readouterr().out)
    assert wins_out["ok"] is True

    assert main(["shot", "--target", "screen", "--grid", "--no-cursor"]) == 0
    shot_out = json.loads(capsys.readouterr().out)
    obs_id = shot_out["observation"]["id"]

    assert (
        main(["zoom", "--obs", obs_id, "--x", "125", "--y", "125", "--w", "63", "--h", "63"]) == 0
    )
    zoom_out = json.loads(capsys.readouterr().out)
    assert zoom_out["observation"]["parent_id"] == obs_id
