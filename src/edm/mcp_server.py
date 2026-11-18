"""MCP stdio server exposing all 23 EDM desktop vision and action tools."""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import ImageContent, TextContent

from edm.actions.addressing import Address
from edm.actions.windowops import WindowActionName
from edm.errors import EdmError, ErrorCode
from edm.geometry import CoordSpace, Rect
from edm.perception.ocr import MatchMode
from edm.service import Edm, Result
from edm.win32.dpi import ensure_dpi_awareness

# Alias for compatibility with mcp 1.x naming in design docs (renamed to MCPServer in mcp 2.x).
FastMCP = MCPServer

ContentItem = TextContent | ImageContent


def _format_result(res: Result) -> list[ContentItem]:
    items: list[ContentItem] = [
        TextContent(type="text", text=json.dumps(res.payload, ensure_ascii=False))
    ]
    if res.image is not None and res.mime is not None:
        b64 = base64.b64encode(res.image).decode("ascii")
        items.append(ImageContent(type="image", data=b64, mime_type=res.mime))
    return items


def _safe_call(fn: Callable[[], Result]) -> list[ContentItem]:
    try:
        return _format_result(fn())
    except EdmError as exc:
        return [TextContent(type="text", text=json.dumps(exc.to_payload(), ensure_ascii=False))]
    except Exception as exc:
        internal = EdmError(ErrorCode.INTERNAL, str(exc))
        return [
            TextContent(type="text", text=json.dumps(internal.to_payload(), ensure_ascii=False))
        ]


def _make_address(
    observation_id: str | None = None,
    x: float | None = None,
    y: float | None = None,
    coord_space: CoordSpace = "pixel",
    mark: int | None = None,
    text: str | None = None,
    target: str = "screen",
    screen_x: int | None = None,
    screen_y: int | None = None,
) -> Address:
    return Address(
        observation_id=observation_id,
        x=x,
        y=y,
        coord_space=coord_space,
        mark=mark,
        text=text,
        target=target,
        screen_x=screen_x,
        screen_y=screen_y,
    )


def build_server(edm: Edm | None = None) -> MCPServer:
    """Create and configure the ``edm`` MCP server with all 23 tools."""
    svc = edm if edm is not None else Edm.build_default()
    srv = MCPServer(
        "edm",
        instructions=(
            "Call doctor once at the start of a session. If ISOLATED_DESKTOP is returned, stop "
            "and inform the user. Prefer non-visual CLI/shortcuts first, then ui_elements (marks), "
            "then find_text (OCR), and finally screenshot + zoom coordinates."
        ),
    )

    @srv.tool(
        name="doctor",
        description=(
            "Inspect desktop session, DPI, monitors, and capture/UIA/OCR backends. "
            "Call this once at session start; stop immediately if ISOLATED_DESKTOP is reported."
        ),
        structured_output=False,
    )
    def doctor() -> list[ContentItem]:
        return _safe_call(svc.doctor)

    @srv.tool(
        name="list_monitors",
        description="List all physical display monitors, their bounds, DPI, and scale factors.",
        structured_output=False,
    )
    def list_monitors() -> list[ContentItem]:
        return _safe_call(svc.list_monitors)

    @srv.tool(
        name="list_windows",
        description=(
            "List visible top-level windows in Z-order. Supports query selectors such as "
            "hwnd:123, pid:456, exe:acad.exe, class:..., title:..., re:..., or plain text."
        ),
        structured_output=False,
    )
    def list_windows(
        query: str | None = None,
        include_minimized: bool = True,
    ) -> list[ContentItem]:
        return _safe_call(
            lambda: svc.list_windows(query=query, include_minimized=include_minimized)
        )

    @srv.tool(
        name="screenshot",
        description=(
            "Capture screen, monitor:N, window:<query>, or region:x,y,w,h and return an "
            "observation. Prefer ui_elements/find_text for clicking. Use zoom for small targets."
        ),
        structured_output=False,
    )
    def screenshot(
        target: str = "screen",
        max_edge: int = 1600,
        grid: bool = False,
        cursor: bool = True,
        marks: bool = False,
        restore: bool = False,
    ) -> list[ContentItem]:
        return _safe_call(
            lambda: svc.screenshot(
                target=target,
                max_edge=max_edge,
                grid=grid,
                cursor=cursor,
                marks=marks,
                restore=restore,
            )
        )

    @srv.tool(
        name="zoom",
        description=(
            "Crop and magnify a sub-region of an existing observation (up to 4x) for precise "
            "clicking on dense UI or CAD viewports. Returned coordinates map directly to screen."
        ),
        structured_output=False,
    )
    def zoom(
        observation_id: str,
        x: float,
        y: float,
        w: float,
        h: float,
        coord_space: CoordSpace = "pixel",
        fresh: bool = False,
        factor: float | None = None,
    ) -> list[ContentItem]:
        return _safe_call(
            lambda: svc.zoom(
                observation_id=observation_id,
                x=x,
                y=y,
                w=w,
                h=h,
                coord_space=coord_space,
                fresh=fresh,
                factor=factor,
            )
        )

    @srv.tool(
        name="ui_elements",
        description=(
            "Collect interactive UI Automation controls for a window and draw numbered Set-of-Mark "
            "boxes on the observation. Prefer clicking by mark (observation_id + mark) over raw xy."
        ),
        structured_output=False,
    )
    def ui_elements(
        window: str | None = None,
        max_elements: int = 150,
    ) -> list[ContentItem]:
        return _safe_call(lambda: svc.ui_elements(window=window, max_elements=max_elements))

    @srv.tool(
        name="find_text",
        description=(
            "Find visible text on screen or inside a window using offline Windows OCR with Turkish "
            "case folding. Use this when UIA elements are unavailable."
        ),
        structured_output=False,
    )
    def find_text(
        query: str,
        target: str = "screen",
        match: MatchMode = "contains",
    ) -> list[ContentItem]:
        return _safe_call(lambda: svc.find_text(query=query, target=target, match=match))

    @srv.tool(
        name="click",
        description=(
            "Click at an addressed target using exactly one mode: (observation_id+x+y), "
            "(observation_id+mark), text, or (screen_x+screen_y). Verifies observation freshness."
        ),
        structured_output=False,
    )
    def click(
        observation_id: str | None = None,
        x: float | None = None,
        y: float | None = None,
        coord_space: CoordSpace = "pixel",
        mark: int | None = None,
        text: str | None = None,
        target: str = "screen",
        screen_x: int | None = None,
        screen_y: int | None = None,
        button: str = "left",
        count: int = 1,
        modifiers: list[str] | None = None,
        verify: bool = True,
        observe: bool = True,
    ) -> list[ContentItem]:
        addr = _make_address(
            observation_id, x, y, coord_space, mark, text, target, screen_x, screen_y
        )
        return _safe_call(
            lambda: svc.click(
                addr,
                button=button,
                count=count,
                modifiers=modifiers,
                verify=verify,
                observe=observe,
            )
        )

    @srv.tool(
        name="move_mouse",
        description="Move the mouse cursor to an addressed target and optionally observe.",
        structured_output=False,
    )
    def move_mouse(
        observation_id: str | None = None,
        x: float | None = None,
        y: float | None = None,
        coord_space: CoordSpace = "pixel",
        mark: int | None = None,
        text: str | None = None,
        target: str = "screen",
        screen_x: int | None = None,
        screen_y: int | None = None,
        verify: bool = True,
        observe: bool = True,
    ) -> list[ContentItem]:
        addr = _make_address(
            observation_id, x, y, coord_space, mark, text, target, screen_x, screen_y
        )
        return _safe_call(lambda: svc.move_mouse(addr, verify=verify, observe=observe))

    @srv.tool(
        name="drag",
        description=(
            "Drag smoothly across 20 intermediate points from from_* address to to_* address. "
            "Releases buttons safely on completion or abort."
        ),
        structured_output=False,
    )
    def drag(
        from_observation_id: str | None = None,
        from_x: float | None = None,
        from_y: float | None = None,
        from_coord_space: CoordSpace = "pixel",
        from_mark: int | None = None,
        from_text: str | None = None,
        from_target: str = "screen",
        from_screen_x: int | None = None,
        from_screen_y: int | None = None,
        to_observation_id: str | None = None,
        to_x: float | None = None,
        to_y: float | None = None,
        to_coord_space: CoordSpace = "pixel",
        to_mark: int | None = None,
        to_text: str | None = None,
        to_target: str = "screen",
        to_screen_x: int | None = None,
        to_screen_y: int | None = None,
        button: str = "left",
        duration_ms: int = 300,
        verify: bool = True,
        observe: bool = True,
    ) -> list[ContentItem]:
        a1 = _make_address(
            from_observation_id,
            from_x,
            from_y,
            from_coord_space,
            from_mark,
            from_text,
            from_target,
            from_screen_x,
            from_screen_y,
        )
        a2 = _make_address(
            to_observation_id,
            to_x,
            to_y,
            to_coord_space,
            to_mark,
            to_text,
            to_target,
            to_screen_x,
            to_screen_y,
        )
        return _safe_call(
            lambda: svc.drag(
                a1,
                a2,
                button=button,
                duration_ms=duration_ms,
                verify=verify,
                observe=observe,
            )
        )

    @srv.tool(
        name="draw_path",
        description=(
            "Trace a continuous multi-point path (up to 200 [x, y] points) in observation "
            "coordinates with optional Catmull-Rom smoothing for CAD/brush drawing."
        ),
        structured_output=False,
    )
    def draw_path(
        observation_id: str,
        points: list[list[float]],
        coord_space: CoordSpace = "pixel",
        button: str = "left",
        press_button: bool = True,
        smooth: bool = False,
        duration_ms: int = 600,
        observe: bool = True,
    ) -> list[ContentItem]:
        def _run() -> Result:
            try:
                pts = [(float(p[0]), float(p[1])) for p in points]
            except (TypeError, ValueError, IndexError) as exc:
                raise EdmError(
                    ErrorCode.INVALID_ARGUMENT,
                    f"Each point in draw_path must be a [x, y] pair: {exc}",
                ) from exc
            return svc.draw_path(
                observation_id,
                pts,
                coord_space=coord_space,
                button=button,
                press_button=press_button,
                smooth=smooth,
                duration_ms=duration_ms,
                observe=observe,
            )

        return _safe_call(_run)

    @srv.tool(
        name="mouse_button",
        description="Press (down) or release (up) a mouse button, optionally at an address.",
        structured_output=False,
    )
    def mouse_button(
        action: Literal["down", "up"],
        button: str = "left",
        observation_id: str | None = None,
        x: float | None = None,
        y: float | None = None,
        coord_space: CoordSpace = "pixel",
        mark: int | None = None,
        text: str | None = None,
        target: str = "screen",
        screen_x: int | None = None,
        screen_y: int | None = None,
        observe: bool = True,
    ) -> list[ContentItem]:
        has_any = any(v is not None for v in (observation_id, x, y, mark, text, screen_x, screen_y))
        addr = (
            _make_address(observation_id, x, y, coord_space, mark, text, target, screen_x, screen_y)
            if has_any
            else None
        )
        return _safe_call(
            lambda: svc.mouse_button(action, button=button, addr=addr, observe=observe)
        )

    @srv.tool(
        name="key_state",
        description="Hold (down) or release (up) a single modifier or key.",
        structured_output=False,
    )
    def key_state(
        key: str,
        action: Literal["down", "up"],
        observe: bool = True,
    ) -> list[ContentItem]:
        return _safe_call(lambda: svc.key_state(key=key, action=action, observe=observe))

    @srv.tool(
        name="scroll",
        description=(
            "Scroll the mouse wheel vertically (dy, + is up) or horizontally (dx) at target."
        ),
        structured_output=False,
    )
    def scroll(
        observation_id: str | None = None,
        x: float | None = None,
        y: float | None = None,
        coord_space: CoordSpace = "pixel",
        mark: int | None = None,
        text: str | None = None,
        target: str = "screen",
        screen_x: int | None = None,
        screen_y: int | None = None,
        dy: int = 0,
        dx: int = 0,
        verify: bool = True,
        observe: bool = True,
    ) -> list[ContentItem]:
        addr = _make_address(
            observation_id, x, y, coord_space, mark, text, target, screen_x, screen_y
        )
        return _safe_call(lambda: svc.scroll(addr, dy=dy, dx=dx, verify=verify, observe=observe))

    @srv.tool(
        name="type_text",
        description=(
            "Type arbitrary Unicode and Turkish text via layout-independent KEYEVENTF_UNICODE. "
            "Focus the target input field before calling."
        ),
        structured_output=False,
    )
    def type_text(
        text: str,
        interval_ms: int = 0,
        observe: bool = True,
    ) -> list[ContentItem]:
        return _safe_call(
            lambda: svc.type_text(text=text, interval_ms=interval_ms, observe=observe)
        )

    @srv.tool(
        name="press_keys",
        description=(
            "Press a keyboard shortcut chord (e.g. 'ctrl+s') or a sequence of chords "
            "(e.g. ['alt', 'f', 'o']). Prefer keyboard shortcuts over visual clicking."
        ),
        structured_output=False,
    )
    def press_keys(
        keys: str | list[str],
        repeat: int = 1,
        observe: bool = True,
    ) -> list[ContentItem]:
        return _safe_call(lambda: svc.press_keys(keys=keys, repeat=repeat, observe=observe))

    @srv.tool(
        name="window_action",
        description=(
            "Manage a window: focus, minimize, maximize, restore, close (polite WM_CLOSE), "
            "move, or resize."
        ),
        structured_output=False,
    )
    def window_action(
        window: str,
        action: WindowActionName,
        rect: list[int] | None = None,
        observe: bool = True,
    ) -> list[ContentItem]:
        def _run() -> Result:
            r: Rect | None = None
            if rect is not None:
                if len(rect) != 4:
                    raise EdmError(
                        ErrorCode.INVALID_ARGUMENT,
                        "rect must be a 4-integer list [x, y, w, h].",
                    )
                r = Rect.from_xywh(int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3]))
            return svc.window_action(window=window, action=action, rect=r, observe=observe)

        return _safe_call(_run)

    @srv.tool(
        name="launch",
        description=(
            "Launch an application by path, Start Menu shortcut name, AUMID, or URL, and "
            "optionally wait for its main window title to stabilize."
        ),
        structured_output=False,
    )
    def launch(
        target: str,
        args: list[str] | None = None,
        wait_window: str | None = None,
        timeout_s: float = 30.0,
        observe: bool = True,
    ) -> list[ContentItem]:
        return _safe_call(
            lambda: svc.launch(
                target=target,
                args=args,
                wait_window=wait_window,
                timeout_s=timeout_s,
                observe=observe,
            )
        )

    @srv.tool(
        name="wait_for",
        description=(
            "Wait up to timeout_s (<= 60s) for a screen change, screen stability, window "
            "appearance/disappearance, or OCR text appearance."
        ),
        structured_output=False,
    )
    def wait_for(
        kind: Literal["change", "stable", "window", "window_gone", "text"],
        target: str = "screen",
        query: str | None = None,
        timeout_s: float = 10.0,
    ) -> list[ContentItem]:
        return _safe_call(
            lambda: svc.wait_for(kind=kind, target=target, query=query, timeout_s=timeout_s)
        )

    @srv.tool(
        name="clipboard",
        description=(
            "Get or set Unicode text (and inspect image presence) on the Windows clipboard."
        ),
        structured_output=False,
    )
    def clipboard(
        op: Literal["get", "set"],
        text: str | None = None,
    ) -> list[ContentItem]:
        return _safe_call(lambda: svc.clipboard(op=op, text=text))

    @srv.tool(
        name="run_sequence",
        description=(
            "Pre-validate and execute up to 25 action/wait_for steps under a single input lock, "
            "capturing one final observation at the end."
        ),
        structured_output=False,
    )
    def run_sequence(
        steps: list[dict[str, Any]],
        stop_on_error: bool = True,
    ) -> list[ContentItem]:
        return _safe_call(lambda: svc.run_sequence(steps=steps, stop_on_error=stop_on_error))

    @srv.tool(
        name="request_user_region",
        description=(
            "Freeze the screen and ask the human user to drag-select a region of interest "
            "(saved with tag 'user_snip')."
        ),
        structured_output=False,
    )
    def request_user_region(
        prompt: str | None = None,
        timeout_s: float = 120.0,
    ) -> list[ContentItem]:
        return _safe_call(lambda: svc.request_user_region(prompt=prompt, timeout_s=timeout_s))

    @srv.tool(
        name="get_user_snips",
        description="Return the most recent user-snipped region observations, newest first.",
        structured_output=False,
    )
    def get_user_snips(limit: int = 1) -> list[ContentItem]:
        return _safe_call(lambda: svc.get_user_snips(limit=limit))

    return srv


def run_stdio(edm: Edm | None = None) -> None:
    """Start the EDM MCP server over stdio with DPI awareness and hotkey killswitch."""
    ensure_dpi_awareness()
    svc = edm if edm is not None else Edm.build_default()
    svc.killswitch.start_hotkey_thread()
    try:
        srv = build_server(svc)
        srv.run(transport="stdio")
    finally:
        svc.killswitch.stop()
