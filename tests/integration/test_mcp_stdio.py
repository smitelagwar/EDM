from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
from io import BytesIO
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import ImageContent, TextContent
from PIL import Image

EXPECTED_23_TOOLS = {
    "doctor",
    "list_monitors",
    "list_windows",
    "screenshot",
    "zoom",
    "ui_elements",
    "find_text",
    "click",
    "move_mouse",
    "drag",
    "draw_path",
    "mouse_button",
    "key_state",
    "scroll",
    "type_text",
    "press_keys",
    "window_action",
    "launch",
    "wait_for",
    "clipboard",
    "run_sequence",
    "request_user_region",
    "get_user_snips",
}


async def _with_mcp_session(tmp_path: Path, fn: Any) -> Any:
    env = dict(os.environ)
    env["EDM_FAKE"] = "1"
    env["EDM_DATA_DIR"] = str(tmp_path / "edm-data")
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "edm", "mcp"],
        env=env,
    )
    async with (
        stdio_client(params) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        return await fn(session)


def test_tools_listed_exact_names(tmp_path: Path) -> None:
    async def _check(session: ClientSession) -> None:
        listed = await session.list_tools()
        names = {t.name for t in listed.tools}
        assert names == EXPECTED_23_TOOLS
        assert len(names) == 23
        for tool in listed.tools:
            assert tool.description and len(tool.description.strip()) > 10

    asyncio.run(asyncio.wait_for(_with_mcp_session(tmp_path, _check), timeout=30.0))


def test_doctor_call(tmp_path: Path) -> None:
    async def _check(session: ClientSession) -> None:
        res = await session.call_tool("doctor", {})
        assert len(res.content) == 1
        first = res.content[0]
        assert isinstance(first, TextContent)
        data = json.loads(first.text)
        assert data["version"] == "0.1.0rc1"
        assert data["session"]["state"] == "ok"

    asyncio.run(asyncio.wait_for(_with_mcp_session(tmp_path, _check), timeout=30.0))


def test_screenshot_returns_image_content(tmp_path: Path) -> None:
    async def _check(session: ClientSession) -> None:
        res = await session.call_tool("screenshot", {"target": "screen"})
        assert len(res.content) == 2
        text_part, img_part = res.content[0], res.content[1]
        assert isinstance(text_part, TextContent)
        assert isinstance(img_part, ImageContent)
        payload = json.loads(text_part.text)
        assert payload["ok"] is True
        assert img_part.mime_type in {"image/png", "image/jpeg"}
        raw = base64.b64decode(img_part.data)
        with Image.open(BytesIO(raw)) as im:
            assert im.size == (1600, 900)

    asyncio.run(asyncio.wait_for(_with_mcp_session(tmp_path, _check), timeout=30.0))


def test_error_payload_not_exception(tmp_path: Path) -> None:
    async def _check(session: ClientSession) -> None:
        res = await session.call_tool(
            "zoom",
            {"observation_id": "o-nonexistent", "x": 10, "y": 10, "w": 50, "h": 50},
        )
        assert len(res.content) == 1
        first = res.content[0]
        assert isinstance(first, TextContent)
        payload = json.loads(first.text)
        assert payload["ok"] is False
        assert payload["error"]["code"] == "OBSERVATION_NOT_FOUND"

    asyncio.run(asyncio.wait_for(_with_mcp_session(tmp_path, _check), timeout=30.0))
