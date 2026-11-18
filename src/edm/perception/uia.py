"""Windows UI Automation element collection with timeout and Set-of-Mark ordering."""

from __future__ import annotations

import math
import threading
from collections import deque
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any, Protocol

from edm.errors import EdmError, ErrorCode
from edm.geometry import Rect
from edm.win32.monitors import virtual_screen

INTERACTIVE_TYPES: frozenset[str] = frozenset(
    {
        "Button",
        "CheckBox",
        "ComboBox",
        "Edit",
        "Hyperlink",
        "ListItem",
        "MenuItem",
        "RadioButton",
        "TabItem",
        "TreeItem",
        "SplitButton",
        "MenuBar",
        "Slider",
        "Spinner",
        "DataItem",
        "Document",
    }
)

_CONTROL_TYPE_SUFFIX = "Control"


@dataclass(frozen=True)
class Element:
    """Interactive UIA element with a 1-based Set-of-Mark index."""

    mark: int
    name: str
    control_type: str
    rect: Rect
    enabled: bool
    automation_id: str
    value: str | None


@dataclass(frozen=True)
class RawElement:
    """Unfiltered element record yielded by an ``ElementProvider``."""

    name: str
    control_type: str
    rect: Rect
    enabled: bool
    visible: bool
    automation_id: str
    value: str | None = None


class ElementProvider(Protocol):
    """Protocol for UIA tree traversal providers (real or fake)."""

    def iter_elements(self, hwnd: int) -> Iterable[RawElement]:
        """Yield ``RawElement`` records for the window *hwnd*."""
        ...


def _normalize_control_type(name: str) -> str:
    if name.endswith(_CONTROL_TYPE_SUFFIX) and len(name) > len(_CONTROL_TYPE_SUFFIX):
        return name[: -len(_CONTROL_TYPE_SUFFIX)]
    return name


_VALUE_PATTERN_ID = 10002


def _read_value(ctrl: Any, pattern_id: int = _VALUE_PATTERN_ID) -> str | None:
    try:
        get_pat = getattr(ctrl, "GetPattern", None)
        if callable(get_pat):
            vp = get_pat(pattern_id)
            if vp is not None:
                return str(vp.Value)
    except Exception:
        pass
    try:
        get_vp = getattr(ctrl, "GetValuePattern", None)
        if callable(get_vp):
            vp = get_vp()
            if vp is not None:
                return str(vp.Value)
    except Exception:
        return None
    return None


class UiaElementProvider:
    """Real Windows UI Automation provider backed by ``uiautomation``."""

    def iter_elements(self, hwnd: int) -> Iterator[RawElement]:
        """Traverse descendants of *hwnd* inside ``UIAutomationInitializerInThread``."""
        try:
            import uiautomation as auto  # type: ignore[import-untyped]
        except Exception as exc:
            raise EdmError(
                ErrorCode.UIA_UNAVAILABLE,
                f"uiautomation package is unavailable: {exc}",
            ) from exc

        try:
            with auto.UIAutomationInitializerInThread():
                root = auto.ControlFromHandle(hwnd)
                if root is None:
                    raise EdmError(
                        ErrorCode.UIA_UNAVAILABLE,
                        f"UIA ControlFromHandle returned None for hwnd={hwnd}.",
                        details={"hwnd": hwnd},
                    )
                queue: deque[Any] = deque([root])
                while queue:
                    ctrl = queue.popleft()
                    try:
                        children = ctrl.GetChildren() or []
                        queue.extend(children)
                    except Exception:
                        pass
                    try:
                        br = ctrl.BoundingRectangle
                        rect = Rect(int(br.left), int(br.top), int(br.right), int(br.bottom))
                        ctype = _normalize_control_type(str(ctrl.ControlTypeName or ""))
                        yield RawElement(
                            name=str(ctrl.Name or ""),
                            control_type=ctype,
                            rect=rect,
                            enabled=bool(ctrl.IsEnabled),
                            visible=not bool(ctrl.IsOffscreen),
                            automation_id=str(ctrl.AutomationId or ""),
                            value=_read_value(ctrl),
                        )
                    except Exception:
                        continue
        except EdmError:
            raise
        except Exception as exc:
            raise EdmError(
                ErrorCode.UIA_UNAVAILABLE,
                f"UIA traversal failed for hwnd={hwnd}: {exc}",
                details={"hwnd": hwnd},
            ) from exc


def collect_elements(
    hwnd: int,
    max_elements: int = 150,
    timeout_s: float = 5.0,
    provider: ElementProvider | None = None,
    screen_bounds: Rect | None = None,
) -> tuple[list[Element], bool]:
    """Collect visible interactive elements for *hwnd* within *timeout_s*."""
    if not math.isfinite(timeout_s) or max_elements <= 0 or timeout_s <= 0:
        raise EdmError(
            ErrorCode.INVALID_ARGUMENT,
            "max_elements and finite timeout_s must be positive.",
        )

    active_provider: ElementProvider = provider if provider is not None else UiaElementProvider()
    bounds = screen_bounds if screen_bounds is not None else virtual_screen()

    collected: list[RawElement] = []
    lock = threading.Lock()
    stop_event = threading.Event()
    errors: list[Exception] = []
    truncated = False

    def _worker() -> None:
        nonlocal truncated
        try:
            for raw in active_provider.iter_elements(hwnd):
                if stop_event.is_set():
                    break
                if not raw.visible:
                    continue
                if raw.rect.width <= 0 or raw.rect.height <= 0:
                    continue
                if raw.rect.intersection(bounds) is None:
                    continue
                if raw.control_type not in INTERACTIVE_TYPES:
                    continue
                with lock:
                    collected.append(raw)
                    if len(collected) >= max_elements:
                        truncated = True
                        break
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join(timeout=timeout_s)
    if thread.is_alive():
        stop_event.set()
        truncated = True
        thread.join(timeout=0.1)

    if errors:
        err = errors[0]
        if isinstance(err, EdmError):
            raise err
        raise EdmError(
            ErrorCode.UIA_UNAVAILABLE,
            f"UIA provider error: {err}",
            details={"hwnd": hwnd},
        ) from err

    with lock:
        snapshot = list(collected)

    snapshot.sort(key=lambda r: (r.rect.top, r.rect.left))
    elements = [
        Element(
            mark=idx + 1,
            name=raw.name,
            control_type=raw.control_type,
            rect=raw.rect,
            enabled=raw.enabled,
            automation_id=raw.automation_id,
            value=raw.value,
        )
        for idx, raw in enumerate(snapshot)
    ]
    return elements, truncated
