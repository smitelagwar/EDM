from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import edm.cli as cli_mod
from edm.cli import main
from edm.service import Result


class _SpyEdm:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def _rec(self, name: str, **kwargs: Any) -> Result:
        self.calls.append((name, kwargs))
        return Result(payload={"ok": True, "action": name, "note": "ğüşıöç"})

    def doctor(self) -> Result:
        return self._rec("doctor")

    def list_monitors(self) -> Result:
        return self._rec("list_monitors")

    def list_windows(self, query: str | None = None, include_minimized: bool = True) -> Result:
        return self._rec("list_windows", query=query, include_minimized=include_minimized)

    def screenshot(self, **kwargs: Any) -> Result:
        return self._rec("screenshot", **kwargs)

    def zoom(self, **kwargs: Any) -> Result:
        return self._rec("zoom", **kwargs)

    def ui_elements(self, **kwargs: Any) -> Result:
        return self._rec("ui_elements", **kwargs)

    def find_text(self, query: str, **kwargs: Any) -> Result:
        return self._rec("find_text", query=query, **kwargs)

    def click(self, addr: Any, **kwargs: Any) -> Result:
        return self._rec("click", addr=addr, **kwargs)

    def move_mouse(self, addr: Any, **kwargs: Any) -> Result:
        return self._rec("move_mouse", addr=addr, **kwargs)

    def drag(self, from_addr: Any, to_addr: Any, **kwargs: Any) -> Result:
        return self._rec("drag", from_addr=from_addr, to_addr=to_addr, **kwargs)

    def draw_path(self, obs_id: str, points: Any, **kwargs: Any) -> Result:
        return self._rec("draw_path", observation_id=obs_id, points=points, **kwargs)

    def mouse_button(self, action: str, **kwargs: Any) -> Result:
        return self._rec("mouse_button", action=action, **kwargs)

    def key_state(self, key: str, action: str, **kwargs: Any) -> Result:
        return self._rec("key_state", key=key, action=action, **kwargs)

    def scroll(self, addr: Any, **kwargs: Any) -> Result:
        return self._rec("scroll", addr=addr, **kwargs)

    def type_text(self, text: str, **kwargs: Any) -> Result:
        return self._rec("type_text", text=text, **kwargs)

    def press_keys(self, keys: Any, **kwargs: Any) -> Result:
        return self._rec("press_keys", keys=keys, **kwargs)

    def window_action(self, window: str, action: str, **kwargs: Any) -> Result:
        return self._rec("window_action", window=window, action=action, **kwargs)

    def launch(self, target: str, **kwargs: Any) -> Result:
        return self._rec("launch", target=target, **kwargs)

    def wait_for(self, kind: str, **kwargs: Any) -> Result:
        return self._rec("wait_for", kind=kind, **kwargs)

    def clipboard(self, op: str, **kwargs: Any) -> Result:
        return self._rec("clipboard", op=op, **kwargs)

    def run_sequence(self, steps: Any, **kwargs: Any) -> Result:
        return self._rec("run_sequence", steps=steps, **kwargs)

    def request_user_region(self, **kwargs: Any) -> Result:
        return self._rec("request_user_region", **kwargs)

    def prune(self) -> Result:
        return self._rec("prune")


@pytest.mark.parametrize(
    ("argv", "expected_method"),
    [
        (["doctor"], "doctor"),
        (["monitors"], "list_monitors"),
        (["windows", "--query", "notepad"], "list_windows"),
        (["shot", "--target", "screen", "--marks"], "screenshot"),
        (["zoom", "--obs", "o-1", "--x", "10", "--y", "20", "--w", "50", "--h", "50"], "zoom"),
        (["elements", "--window", "notepad"], "ui_elements"),
        (["find-text", "Tamam"], "find_text"),
        (["click", "--screen", "100", "200"], "click"),
        (["move", "--screen", "100", "200"], "move_mouse"),
        (["drag", "--from-screen", "10", "20", "--to-screen", "30", "40"], "drag"),
        (["draw-path", "--obs", "o-1", "--points", "[[10,20],[30,40]]"], "draw_path"),
        (["mouse-btn", "down", "--screen", "50", "60"], "mouse_button"),
        (["key-state", "ctrl", "down"], "key_state"),
        (["scroll", "--screen", "100", "200", "--dy", "3"], "scroll"),
        (["type", "--text", "Merhaba ğ"], "type_text"),
        (["keys", "ctrl+s"], "press_keys"),
        (["window", "notepad", "focus"], "window_action"),
        (["launch", "notepad.exe"], "launch"),
        (["wait", "stable"], "wait_for"),
        (["clip", "get"], "clipboard"),
        (["seq", "--steps", '[{"tool":"type_text","args":{"text":"a"}}]'], "run_sequence"),
        (["snip", "--prompt", "Seç"], "request_user_region"),
        (["prune"], "prune"),
    ],
)
def test_every_subcommand_parses(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    expected_method: str,
) -> None:
    spy = _SpyEdm()
    monkeypatch.setattr(cli_mod.Edm, "build_default", classmethod(lambda _cls, _cfg=None: spy))
    rc = main(argv)
    out = capsys.readouterr().out
    assert rc == 0
    assert len(spy.calls) == 1
    assert spy.calls[0][0] == expected_method
    parsed = json.loads(out)
    assert parsed["ok"] is True


def test_json_utf8_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spy = _SpyEdm()
    monkeypatch.setattr(cli_mod.Edm, "build_default", classmethod(lambda _cls, _cfg=None: spy))
    assert main(["doctor"]) == 0
    raw_out = capsys.readouterr().out
    assert "ğüşıöç" in raw_out
    assert "\\u011f" not in raw_out


def test_exit_code_on_edm_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("EDM_FAKE", "1")
    monkeypatch.setenv("EDM_DATA_DIR", str(tmp_path / "edm-data"))

    rc = main(["click", "--obs", "o-missing", "--x", "10", "--y", "10"])
    captured = capsys.readouterr()
    assert rc == 2
    err = json.loads(captured.err)
    assert err["ok"] is False
    assert err["error"]["code"] == "OBSERVATION_NOT_FOUND"

    # Malformed draw-path points also return exit code 2 with INVALID_ARGUMENT
    rc2 = main(["draw-path", "--obs", "o-1", "--points", '["bad"]'])
    err2 = json.loads(capsys.readouterr().err)
    assert rc2 == 2
    assert err2["error"]["code"] == "INVALID_ARGUMENT"


def test_exit_code_on_unexpected_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def _boom(*_a: Any, **_kw: Any) -> Any:
        raise RuntimeError("unexpected boom")

    monkeypatch.setattr(cli_mod, "_dispatch", _boom)
    rc = main(["doctor"])
    captured = capsys.readouterr()
    assert rc == 1
    err = json.loads(captured.err)
    assert err["ok"] is False
    assert err["error"]["code"] == "INTERNAL"


def test_non_win32_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli_mod.sys, "platform", "linux")
    rc = main(["doctor"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "EDM yalnızca Windows'ta çalışır" in captured.err


def test_mcp_and_serve_http_subparsers_exist() -> None:
    parser = cli_mod.build_parser()
    ns_mcp = parser.parse_args(["mcp"])
    assert ns_mcp.command == "mcp"
    ns_http = parser.parse_args(["serve-http", "--host", "127.0.0.1", "--port", "8765"])
    assert ns_http.command == "serve-http"
    assert ns_http.port == 8765
