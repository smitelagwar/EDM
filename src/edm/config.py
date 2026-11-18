"""Configuration dataclass and TOML loader for EDM."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from edm.errors import EdmError, ErrorCode


def default_data_dir() -> Path:
    """Return the default EDM runtime data directory."""
    env_dir = os.environ.get("EDM_DATA_DIR")
    if env_dir:
        return Path(env_dir)
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / "EDM"
    return Path.home() / "AppData" / "Local" / "EDM"


def _default_config_path() -> Path:
    env_cfg = os.environ.get("EDM_CONFIG")
    if env_cfg:
        return Path(env_cfg)
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "EDM" / "config.toml"
    return Path.home() / "AppData" / "Roaming" / "EDM" / "config.toml"


@dataclass(frozen=True)
class Config:
    """Immutable runtime configuration for EDM."""

    preview_max_edge: int = 1600
    max_image_bytes: int = 1_500_000
    observation_ttl_s: int = 120
    stale_patch_px: int = 24
    stale_threshold: float = 0.15
    settle_quiet_ms: int = 300
    settle_timeout_ms: int = 3000
    retention_days: int = 7
    retention_bytes: int = 2_000_000_000
    killswitch_hotkey: str = "ctrl+alt+shift+f12"
    failsafe_corner: bool = True
    input_lock_timeout_s: float = 10.0
    uia_timeout_s: float = 5.0
    wgc_timeout_s: float = 3.0
    data_dir: Path = field(default_factory=default_data_dir)


_INT_FIELDS = {
    "preview_max_edge",
    "max_image_bytes",
    "observation_ttl_s",
    "stale_patch_px",
    "settle_quiet_ms",
    "settle_timeout_ms",
    "retention_days",
    "retention_bytes",
}
_FLOAT_FIELDS = {
    "stale_threshold",
    "input_lock_timeout_s",
    "uia_timeout_s",
    "wgc_timeout_s",
}
_BOOL_FIELDS = {"failsafe_corner"}
_STR_FIELDS = {"killswitch_hotkey"}
_PATH_FIELDS = {"data_dir"}
_KNOWN_FIELDS = {f.name for f in fields(Config)}


def _validate_value(key: str, value: Any) -> Any:
    if key in _INT_FIELDS:
        if isinstance(value, bool) or not isinstance(value, int):
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"Config key '{key}' must be an integer.",
                details={"key": key, "type": type(value).__name__},
            )
        return value
    if key in _FLOAT_FIELDS:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"Config key '{key}' must be a number.",
                details={"key": key, "type": type(value).__name__},
            )
        return float(value)
    if key in _BOOL_FIELDS:
        if not isinstance(value, bool):
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"Config key '{key}' must be a boolean.",
                details={"key": key, "type": type(value).__name__},
            )
        return value
    if key in _STR_FIELDS:
        if not isinstance(value, str):
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"Config key '{key}' must be a string.",
                details={"key": key, "type": type(value).__name__},
            )
        return value
    if key in _PATH_FIELDS:
        if not isinstance(value, (str, Path)) or (isinstance(value, str) and not value.strip()):
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"Config key '{key}' must be a non-empty path string.",
                details={"key": key, "type": type(value).__name__},
            )
        return Path(value)
    raise EdmError(
        ErrorCode.INVALID_ARGUMENT,
        f"Unknown config key: '{key}'.",
        details={"key": key},
    )


def load_config(path: Path | None = None) -> Config:
    """Load EDM configuration from TOML, falling back to defaults when no file exists."""
    if path is not None:
        if not path.is_file():
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"Config file not found: {path}",
                details={"path": str(path)},
            )
        target = path
    else:
        target = _default_config_path()
        if not target.is_file():
            return Config()

    try:
        with target.open("rb") as fh:
            raw = tomllib.load(fh)
    except (tomllib.TOMLDecodeError, OSError) as exc:
        raise EdmError(
            ErrorCode.INVALID_ARGUMENT,
            f"Failed to parse config file {target}: {exc}",
            details={"path": str(target)},
        ) from exc

    validated: dict[str, Any] = {}
    for key, value in raw.items():
        if key not in _KNOWN_FIELDS:
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"Unknown config key: '{key}'.",
                details={"key": key},
            )
        validated[key] = _validate_value(key, value)

    return Config(**validated)
