from pathlib import Path

import pytest

from edm.actions.launch import LaunchSpec, resolve_launch_target
from edm.errors import EdmError, ErrorCode


def test_resolve_launch_path(tmp_path: Path) -> None:
    exe = tmp_path / "app.exe"
    exe.write_bytes(b"MZ")
    spec = resolve_launch_target(str(exe), start_menu_dirs=[], aumid_lookup=lambda _q: None)
    assert spec == LaunchSpec(kind="path", value=str(exe))


def test_resolve_launch_url() -> None:
    spec = resolve_launch_target(
        "https://example.com",
        start_menu_dirs=[],
        aumid_lookup=lambda _q: None,
    )
    assert spec == LaunchSpec(kind="url", value="https://example.com")


def test_resolve_launch_shortcut_fold(tmp_path: Path) -> None:
    lnk1 = tmp_path / "AutoCAD 2026 - Türkçe.lnk"
    lnk2 = tmp_path / "AutoCAD 2026 - Türkçe Yardım Rehberi.lnk"
    lnk1.write_bytes(b"LNK")
    lnk2.write_bytes(b"LNK")

    spec = resolve_launch_target(
        "autocad",
        start_menu_dirs=[tmp_path],
        aumid_lookup=lambda _q: None,
    )
    assert spec == LaunchSpec(kind="shortcut", value=str(lnk1))


def test_resolve_launch_not_found(tmp_path: Path) -> None:
    with pytest.raises(EdmError) as exc_info:
        resolve_launch_target(
            "nonexistent-app-xyz",
            start_menu_dirs=[tmp_path],
            aumid_lookup=lambda _q: None,
        )
    assert exc_info.value.code == ErrorCode.WINDOW_NOT_FOUND
    assert "uygulama bulunamadı" in exc_info.value.message
