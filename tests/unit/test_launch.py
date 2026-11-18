from dataclasses import replace
from pathlib import Path

import pytest

from edm.actions.launch import LaunchSpec, resolve_launch_target
from edm.actions.windowops import window_action as real_window_action
from edm.config import Config
from edm.errors import EdmError, ErrorCode
from edm.fakes import (
    FakeCaptureBackend,
    FakeClipboard,
    FakeInputSink,
    FakeSession,
    fake_cursor_position,
    fake_monitors,
    fake_virtual_screen,
    fake_windows,
)
from edm.service import Edm
from edm.win32.process import Integrity


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


def test_window_action_guard_and_uipi(tmp_path: Path) -> None:
    calls: list[tuple[int, str]] = []
    elevated = False

    def _win_provider() -> list:
        w = fake_windows()[0]
        return [replace(w, integrity=Integrity.high if elevated else Integrity.medium)]

    def _win_act(hwnd: int, act: str, rect: object) -> None:
        if act == "move" and rect is None:
            raise EdmError(ErrorCode.INVALID_ARGUMENT, "rect required")
        calls.append((hwnd, act))

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
        clipboard_backend=FakeClipboard(),
        window_action_fn=_win_act,
        launcher_fn=lambda _spec, _args: None,
    )

    res = edm.window_action("exe:fake.exe", "focus", observe=False)
    assert res.payload["ok"] is True
    assert calls == [(1001, "focus")]

    with pytest.raises(EdmError) as exc_move:
        edm.window_action("exe:fake.exe", "move", rect=None, observe=False)
    assert exc_move.value.code == ErrorCode.INVALID_ARGUMENT

    elevated = True
    with pytest.raises(EdmError) as exc_uipi:
        edm.window_action("exe:fake.exe", "close", observe=False)
    assert exc_uipi.value.code == ErrorCode.ELEVATION_REQUIRED
    assert calls == [(1001, "focus")]
    assert real_window_action is not None


def test_service_launch_wait_window_and_timeout(tmp_path: Path) -> None:
    exe = tmp_path / "demo.exe"
    exe.write_bytes(b"MZ")
    launched = False

    def _win_provider() -> list:
        base = fake_windows()
        if not launched:
            return base
        return base + [replace(base[0], hwnd=2002, title="Demo App", z_order=1)]

    def _launcher(_spec: LaunchSpec, _args: list[str] | None) -> None:
        nonlocal launched
        launched = True

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
        clipboard_backend=FakeClipboard(),
        window_action_fn=lambda _h, _a, _r: None,
        launcher_fn=_launcher,
    )

    with pytest.raises(EdmError) as exc_nan:
        edm.launch(str(exe), timeout_s=float("nan"), observe=False)
    assert exc_nan.value.code == ErrorCode.INVALID_ARGUMENT

    res = edm.launch(str(exe), wait_window="^Demo.*", timeout_s=3.0, observe=False)
    assert res.payload["ok"] is True
    assert res.payload["details"]["window"]["hwnd"] == 2002

    with pytest.raises(EdmError) as exc_to:
        edm.launch(str(exe), wait_window="^NeverAppears$", timeout_s=0.2, observe=False)
    assert exc_to.value.code == ErrorCode.TIMEOUT
