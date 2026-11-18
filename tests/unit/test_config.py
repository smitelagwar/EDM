from pathlib import Path

import pytest

from edm.config import Config, load_config
from edm.errors import EdmError, ErrorCode


def test_config_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("EDM_DATA_DIR", raising=False)
    monkeypatch.delenv("EDM_CONFIG", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))

    cfg = load_config()
    assert isinstance(cfg, Config)
    assert cfg.preview_max_edge == 1600
    assert cfg.max_image_bytes == 1_500_000
    assert cfg.observation_ttl_s == 120
    assert cfg.stale_patch_px == 24
    assert cfg.stale_threshold == 0.15
    assert cfg.settle_quiet_ms == 300
    assert cfg.settle_timeout_ms == 3000
    assert cfg.retention_days == 7
    assert cfg.retention_bytes == 2_000_000_000
    assert cfg.killswitch_hotkey == "ctrl+alt+shift+f12"
    assert cfg.failsafe_corner is True
    assert cfg.input_lock_timeout_s == 10.0
    assert cfg.uia_timeout_s == 5.0
    assert cfg.wgc_timeout_s == 3.0
    assert cfg.data_dir == tmp_path / "local" / "EDM"


def test_config_toml_override(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text("preview_max_edge = 2000\nfailsafe_corner = false\n", encoding="utf-8")

    cfg = load_config(cfg_file)
    assert cfg.preview_max_edge == 2000
    assert cfg.failsafe_corner is False
    assert cfg.observation_ttl_s == 120


def test_config_unknown_key_rejected(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text("unknown_setting = 42\n", encoding="utf-8")

    with pytest.raises(EdmError) as exc_info:
        load_config(cfg_file)
    assert exc_info.value.code == ErrorCode.INVALID_ARGUMENT


@pytest.mark.parametrize(
    "toml_body",
    [
        "preview_max_edge = true\n",
        'preview_max_edge = "1600"\n',
        "failsafe_corner = 1\n",
        "stale_threshold = false\n",
        "killswitch_hotkey = 123\n",
        "data_dir = 42\n",
    ],
)
def test_config_type_mismatch_rejected(tmp_path: Path, toml_body: str) -> None:
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(toml_body, encoding="utf-8")

    with pytest.raises(EdmError) as exc_info:
        load_config(cfg_file)
    assert exc_info.value.code == ErrorCode.INVALID_ARGUMENT


def test_config_explicit_missing_path_rejected(tmp_path: Path) -> None:
    with pytest.raises(EdmError) as exc_info:
        load_config(tmp_path / "missing.toml")
    assert exc_info.value.code == ErrorCode.INVALID_ARGUMENT


def test_config_invalid_toml_rejected(tmp_path: Path) -> None:
    cfg_file = tmp_path / "bad.toml"
    cfg_file.write_text("preview_max_edge = [unclosed\n", encoding="utf-8")

    with pytest.raises(EdmError) as exc_info:
        load_config(cfg_file)
    assert exc_info.value.code == ErrorCode.INVALID_ARGUMENT


def test_env_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    custom_dir = tmp_path / "custom-edm-data"
    monkeypatch.setenv("EDM_DATA_DIR", str(custom_dir))
    monkeypatch.delenv("EDM_CONFIG", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))

    cfg = load_config()
    assert cfg.data_dir == custom_dir
