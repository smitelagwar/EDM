"""User-started loopback Streamable HTTP MCP server with token and Origin guards."""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import uvicorn

from edm.errors import EdmError, ErrorCode
from edm.mcp_server import build_server
from edm.service import Edm
from edm.win32.dpi import ensure_dpi_awareness

_ALLOWED_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "::1"})


def default_token_path() -> Path:
    """Return the default HTTP bearer token file path under ``%APPDATA%\\EDM``."""
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return base / "EDM" / "http-token"


def ensure_http_token(token_path: Path | None = None) -> tuple[str, bool]:
    """Load or generate the loopback HTTP bearer token, printing it once on creation."""
    target = token_path if token_path is not None else default_token_path()
    if target.is_file():
        existing = target.read_text(encoding="utf-8").strip()
        if existing:
            return existing, False

    token = secrets.token_urlsafe(32)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(token + "\n", encoding="utf-8")
    print(f"EDM HTTP bearer token generated at {target}: {token}")
    return token, True


def _is_loopback_origin(origin: str) -> bool:
    parsed = urlparse(origin)
    return parsed.scheme in {"http", "https"} and parsed.hostname in _ALLOWED_HOSTS


async def _send_json_error(
    send: Any,
    status: int,
    message: str,
    *,
    www_authenticate: bool = False,
) -> None:
    body = json.dumps({"ok": False, "error": message}).encode("utf-8")
    headers: list[tuple[bytes, bytes]] = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode("ascii")),
    ]
    if www_authenticate:
        headers.append((b"www-authenticate", b"Bearer"))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


class _LoopbackAuthASGIApp:
    """ASGI wrapper enforcing loopback Origin check and Bearer token authentication."""

    def __init__(self, inner: Any, token: str) -> None:
        self._inner = inner
        self._token = token

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self._inner(scope, receive, send)
            return

        raw_headers = scope.get("headers") or []
        headers = {
            bytes(k).decode("latin1").lower(): bytes(v).decode("latin1") for k, v in raw_headers
        }

        origin = headers.get("origin")
        if origin is not None and not _is_loopback_origin(origin):
            await _send_json_error(send, 403, "Forbidden non-loopback Origin header.")
            return

        auth = headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            await _send_json_error(
                send,
                401,
                "Missing Bearer Authorization header.",
                www_authenticate=True,
            )
            return

        provided = auth[7:].strip()
        if not provided or not secrets.compare_digest(provided, self._token):
            await _send_json_error(
                send,
                401,
                "Invalid Bearer token.",
                www_authenticate=True,
            )
            return

        await self._inner(scope, receive, send)


def validate_loopback_host(host: str) -> None:
    """Ensure *host* is strictly ``127.0.0.1`` or ``::1``."""
    if host not in _ALLOWED_HOSTS:
        raise EdmError(
            ErrorCode.INVALID_ARGUMENT,
            f"EDM HTTP server only binds to loopback (127.0.0.1 or ::1), got {host!r}.",
            details={"host": host},
        )


def build_http_app(
    token: str,
    *,
    edm: Edm | None = None,
    host: str = "127.0.0.1",
) -> Any:
    """Build the guarded Streamable HTTP ASGI application."""
    validate_loopback_host(host)
    if not token.strip():
        raise EdmError(ErrorCode.INVALID_ARGUMENT, "HTTP bearer token must not be empty.")
    srv = build_server(edm)
    inner = srv.streamable_http_app(
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        host=host,
    )
    return _LoopbackAuthASGIApp(inner, token.strip())


def run_http(
    host: str = "127.0.0.1",
    port: int = 8765,
    token_path: Path | None = None,
) -> None:
    """Run the user-started loopback Streamable HTTP MCP server."""
    validate_loopback_host(host)
    if port <= 0 or port > 65535:
        raise EdmError(
            ErrorCode.INVALID_ARGUMENT,
            f"Invalid port: {port}",
            details={"port": port},
        )
    ensure_dpi_awareness()
    token, _ = ensure_http_token(token_path)
    svc = Edm.build_default()
    svc.killswitch.start_hotkey_thread()
    try:
        app = build_http_app(token, edm=svc, host=host)
        uvicorn.run(app, host=host, port=port, log_level="info")
    finally:
        svc.killswitch.stop()
