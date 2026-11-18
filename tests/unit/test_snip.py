"""Unit tests for user-drawn region snipping overlay."""

from __future__ import annotations

from typing import Any

import pytest
from PIL import Image

from edm.geometry import Point, Rect
from edm.snip.overlay import normalize_drag, run_snip


@pytest.mark.parametrize(
    ("p1", "p2", "expected"),
    [
        (Point(300, 200), Point(100, 50), Rect(100, 50, 300, 200)),
        (Point(100, 50), Point(300, 200), Rect(100, 50, 300, 200)),
        (Point(300, 50), Point(100, 200), Rect(100, 50, 300, 200)),
        (Point(100, 200), Point(300, 50), Rect(100, 50, 300, 200)),
        (Point(-100, -200), Point(-400, -500), Rect(-400, -500, -100, -200)),
    ],
)
def test_normalize_drag_any_direction(p1: Point, p2: Point, expected: Rect) -> None:
    """Dragging in any diagonal direction normalizes to (min_x, min_y, max_x, max_y)."""
    assert normalize_drag(p1, p2) == expected


@pytest.mark.parametrize(
    ("p1", "p2", "min_size"),
    [
        (Point(100, 100), Point(100, 100), 4),
        (Point(100, 100), Point(103, 150), 4),
        (Point(100, 100), Point(150, 103), 4),
        (Point(103, 150), Point(100, 100), 4),
        (Point(0, 0), Point(9, 20), 10),
    ],
)
def test_normalize_drag_too_small(p1: Point, p2: Point, min_size: int) -> None:
    """Drags smaller than min_size in width or height return None."""
    assert normalize_drag(p1, p2, min_size=min_size) is None


def test_normalize_drag_exact_min_size() -> None:
    """Drags with width and height equal to min_size are accepted."""
    assert normalize_drag(Point(10, 20), Point(14, 24), min_size=4) == Rect(10, 20, 14, 24)
    assert normalize_drag(Point(10, 20), Point(11, 21), min_size=1) == Rect(10, 20, 11, 21)


def test_run_snip_non_positive_timeout_calls_dpi_and_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-positive timeout ensures DPI awareness and returns None immediately."""
    calls: list[str] = []
    monkeypatch.setattr(
        "edm.snip.overlay.ensure_dpi_awareness",
        lambda: calls.append("dpi") or "per_monitor_v2",
    )
    img = Image.new("RGB", (100, 80), (40, 40, 40))
    assert run_snip(img, Rect(0, 0, 100, 80), timeout_s=0.0) is None
    assert calls == ["dpi"]


def test_run_snip_configures_dpi_and_window_before_mainloop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_snip enables DPI awareness before creating the borderless topmost Tk window."""
    events: list[tuple[str, Any]] = []
    bindings: dict[str, Any] = {}

    class FakeCanvas:
        def __init__(self, master: Any, **kwargs: Any) -> None:
            events.append(("canvas", kwargs))

        def pack(self, **kwargs: Any) -> None:
            events.append(("pack", kwargs))

        def create_image(self, *args: Any, **kwargs: Any) -> int:
            return 1

        def create_rectangle(self, *args: Any, **kwargs: Any) -> int:
            return 2

        def create_text(self, *args: Any, **kwargs: Any) -> int:
            events.append(("prompt", kwargs.get("text")))
            return 3

        def delete(self, *args: Any) -> None:
            pass

        def bind(self, seq: str, fn: Any) -> None:
            bindings[seq] = fn

    class FakeRoot:
        def __init__(self) -> None:
            events.append(("tk_init", None))

        def overrideredirect(self, flag: bool) -> None:
            events.append(("overrideredirect", flag))

        def attributes(self, name: str, val: Any) -> None:
            events.append(("attributes", (name, val)))

        def geometry(self, spec: str) -> None:
            events.append(("geometry", spec))

        def bind(self, seq: str, fn: Any) -> None:
            bindings[seq] = fn

        def bind_all(self, seq: str, fn: Any) -> None:
            bindings[seq] = fn

        def focus_force(self) -> None:
            events.append(("focus_force", None))

        def after(self, ms: int, fn: Any) -> str:
            events.append(("after", ms))
            return "timer-1"

        def after_cancel(self, timer_id: str) -> None:
            events.append(("after_cancel", timer_id))

        def mainloop(self) -> None:
            events.append(("mainloop", None))
            # Simulate drag from (20, 30) to (120, 110) in canvas coordinates.
            press_evt = type("Evt", (), {"x": 20, "y": 30})()
            motion_evt = type("Evt", (), {"x": 120, "y": 110})()
            release_evt = type("Evt", (), {"x": 120, "y": 110})()
            bindings["<ButtonPress-1>"](press_evt)
            bindings["<B1-Motion>"](motion_evt)
            bindings["<ButtonRelease-1>"](release_evt)

        def destroy(self) -> None:
            events.append(("destroy", None))

    monkeypatch.setattr(
        "edm.snip.overlay.ensure_dpi_awareness",
        lambda: events.append(("dpi", None)) or "per_monitor_v2",
    )
    monkeypatch.setattr("edm.snip.overlay.tk.Tk", FakeRoot)
    monkeypatch.setattr("edm.snip.overlay.tk.Canvas", FakeCanvas)
    monkeypatch.setattr("edm.snip.overlay.ImageTk.PhotoImage", lambda img: object())

    img = Image.new("RGB", (200, 150), (80, 80, 80))
    virtual = Rect(-100, 50, 100, 200)
    result = run_snip(img, virtual, prompt="Select region", timeout_s=10.0)

    assert result == Rect(-80, 80, 20, 160)
    assert events.index(("dpi", None)) < events.index(("tk_init", None))
    assert ("overrideredirect", True) in events
    assert ("attributes", ("-topmost", True)) in events
    assert ("geometry", "200x150+-100+50") in events
    assert ("prompt", "Select region") in events


@pytest.mark.parametrize("cancel_mode", ["escape", "timeout"])
def test_run_snip_cancel_and_timeout_return_none(
    monkeypatch: pytest.MonkeyPatch,
    cancel_mode: str,
) -> None:
    """Pressing Escape or hitting timeout_s cancels the overlay and returns None."""
    bindings: dict[str, Any] = {}
    callbacks: dict[str, Any] = {}
    destroyed = False

    class FakeCanvas:
        def __init__(self, master: Any, **kwargs: Any) -> None:
            pass

        def pack(self, **kwargs: Any) -> None:
            pass

        def create_image(self, *args: Any, **kwargs: Any) -> int:
            return 1

        def delete(self, *args: Any) -> None:
            pass

        def bind(self, seq: str, fn: Any) -> None:
            bindings[seq] = fn

    class FakeRoot:
        def overrideredirect(self, flag: bool) -> None:
            pass

        def attributes(self, name: str, val: Any) -> None:
            pass

        def geometry(self, spec: str) -> None:
            pass

        def bind(self, seq: str, fn: Any) -> None:
            bindings[seq] = fn

        def bind_all(self, seq: str, fn: Any) -> None:
            bindings[seq] = fn

        def focus_force(self) -> None:
            pass

        def after(self, ms: int, fn: Any) -> str:
            callbacks["timeout"] = fn
            return "timer-1"

        def after_cancel(self, timer_id: str) -> None:
            pass

        def mainloop(self) -> None:
            if cancel_mode == "escape":
                bindings["<Escape>"](object())
            else:
                callbacks["timeout"]()

        def destroy(self) -> None:
            nonlocal destroyed
            destroyed = True

    monkeypatch.setattr("edm.snip.overlay.ensure_dpi_awareness", lambda: "per_monitor_v2")
    monkeypatch.setattr("edm.snip.overlay.tk.Tk", FakeRoot)
    monkeypatch.setattr("edm.snip.overlay.tk.Canvas", FakeCanvas)
    monkeypatch.setattr("edm.snip.overlay.ImageTk.PhotoImage", lambda img: object())

    img = Image.new("RGB", (100, 100), (50, 50, 50))
    assert run_snip(img, Rect(0, 0, 100, 100), timeout_s=5.0) is None
    assert destroyed is True
