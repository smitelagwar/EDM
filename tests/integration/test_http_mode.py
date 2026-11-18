from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from edm.errors import EdmError, ErrorCode
from edm.http_server import build_http_app, ensure_http_token, run_http
from edm.service import Edm


def test_rejects_non_loopback_host(tmp_path: Path) -> None:
    token_path = tmp_path / "http-token"
    for bad_host in ("0.0.0.0", "192.168.1.10", "localhost", "example.com"):
        with pytest.raises(EdmError) as exc_info:
            run_http(host=bad_host, port=8765, token_path=token_path)
        assert exc_info.value.code == ErrorCode.INVALID_ARGUMENT


def test_token_file_generation(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    token_path = tmp_path / "roaming" / "EDM" / "http-token"
    tok1, created1 = ensure_http_token(token_path)
    out1 = capsys.readouterr().out
    assert created1 is True
    assert len(tok1) >= 32
    assert tok1 in out1

    tok2, created2 = ensure_http_token(token_path)
    out2 = capsys.readouterr().out
    assert created2 is False
    assert tok2 == tok1
    assert out2 == ""


def test_401_without_token(fake_edm: Edm) -> None:
    app = build_http_app("secret-token-123", edm=fake_edm)
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        r1 = client.post(
            "/mcp",
            headers={"Accept": "application/json, text/event-stream"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        assert r1.status_code == 401

        r2 = client.post(
            "/mcp",
            headers={
                "Authorization": "Bearer wrong-token",
                "Accept": "application/json, text/event-stream",
            },
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        assert r2.status_code == 401


def test_403_foreign_origin(fake_edm: Edm) -> None:
    app = build_http_app("secret-token-123", edm=fake_edm)
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        r = client.post(
            "/mcp",
            headers={
                "Authorization": "Bearer secret-token-123",
                "Origin": "https://evil.example.com",
                "Accept": "application/json, text/event-stream",
            },
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        assert r.status_code == 403


def test_tools_list_with_token(fake_edm: Edm) -> None:
    app = build_http_app("secret-token-123", edm=fake_edm)
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        r = client.post(
            "/mcp",
            headers={
                "Authorization": "Bearer secret-token-123",
                "Origin": "http://127.0.0.1:8765",
                "Accept": "application/json, text/event-stream",
            },
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        assert r.status_code == 200
        tools = r.json()["result"]["tools"]
        assert len(tools) == 23
