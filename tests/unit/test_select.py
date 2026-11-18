from __future__ import annotations

import time

import pytest
from PIL import Image

from edm.capture.base import Frame
from edm.capture.select import Capturer, CaptureTarget, parse_target
from edm.config import Config
from edm.errors import EdmError, ErrorCode
from edm.geometry import Rect
from edm.win32.process import Integrity
from edm.win32.windows import WindowInfo


def _good_image(w: int = 200, h: int = 100) -> Image.Image:
    img = Image.new("RGB", (w, h), (240, 240, 240))
    img.paste((20, 20, 20), (0, 0, w, 20))
    return img


def _blank_image(w: int = 200, h: int = 100) -> Image.Image:
    return Image.new("RGB", (w, h), (0, 0, 0))


def _make_window(*, hwnd: int = 101, minimized: bool = False) -> WindowInfo:
    return WindowInfo(
        hwnd=hwnd,
        title="Mock App",
        class_name="MockClass",
        pid=999,
        exe="mock.exe",
        rect=Rect(0, 0, 200, 100),
        minimized=minimized,
        maximized=False,
        visible=True,
        cloaked=False,
        topmost=False,
        foreground=True,
        monitor_index=0,
        integrity=Integrity.medium,
        z_order=0,
    )


class _StubBackend:
    def __init__(
        self,
        name: str,
        *,
        image: Image.Image | None = None,
        error: EdmError | None = None,
        is_available: bool = True,
    ) -> None:
        self.name = name
        self._image = image
        self._error = error
        self._is_available = is_available
        self.calls = 0

    def available(self) -> tuple[bool, str]:
        return (self._is_available, "ok" if self._is_available else "unavailable")

    def capture_rect(self, rect: Rect) -> Frame:
        self.calls += 1
        if self._error is not None:
            raise self._error
        assert self._image is not None
        return Frame(
            image=self._image,
            screen_rect=rect,
            backend=self.name,
            captured_at=time.time(),
            attempts=[],
        )

    def capture_window(self, hwnd: int) -> Frame:
        self.calls += 1
        if self._error is not None:
            raise self._error
        assert self._image is not None
        return Frame(
            image=self._image,
            screen_rect=Rect(0, 0, self._image.width, self._image.height),
            backend=self.name,
            captured_at=time.time(),
            attempts=[],
        )


def test_parse_target_variants() -> None:
    assert parse_target("screen") == CaptureTarget(kind="screen")
    assert parse_target("monitor:1") == CaptureTarget(kind="monitor", monitor=1)
    assert parse_target("window:exe:acad.exe") == CaptureTarget(kind="window", query="exe:acad.exe")
    assert parse_target("region:10,20,300,200") == CaptureTarget(
        kind="region", rect=Rect(10, 20, 310, 220)
    )

    for bad in (
        "",
        "unknown",
        "monitor:abc",
        "monitor:-1",
        "window:",
        "region:1,2,3",
        "region:1,2,0,5",
    ):
        with pytest.raises(EdmError) as exc_info:
            parse_target(bad)
        assert exc_info.value.code == ErrorCode.INVALID_ARGUMENT


def test_capturer_screen_uses_gdi(monkeypatch: pytest.MonkeyPatch) -> None:
    import edm.capture.select as sel

    monkeypatch.setattr(sel, "virtual_screen", lambda: Rect(0, 0, 1920, 1080))
    gdi = _StubBackend("gdi", image=_good_image(1920, 1080))
    capturer = Capturer({"gdi": gdi}, Config())
    frame, win = capturer.capture(CaptureTarget(kind="screen"))
    assert win is None
    assert frame.backend == "gdi"
    assert gdi.calls == 1


def test_capturer_falls_back_on_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    import edm.capture.select as sel

    win = _make_window(hwnd=101)
    monkeypatch.setattr(sel, "resolve_window", lambda _q: (win, []))
    monkeypatch.setattr(sel, "visible_fraction", lambda *_args, **_kwargs: 1.0)
    monkeypatch.setattr(sel, "root_window_at", lambda _p: 101)

    gdi = _StubBackend("gdi", image=_blank_image())
    wgc = _StubBackend("wgc", error=EdmError(ErrorCode.CAPTURE_FAILED, "wgc timeout"))
    pw = _StubBackend("printwindow", image=_good_image())

    capturer = Capturer({"gdi": gdi, "wgc": wgc, "printwindow": pw}, Config())
    frame, returned_win = capturer.capture(CaptureTarget(kind="window", query="Mock"))
    assert returned_win == win
    assert frame.backend == "printwindow"
    assert len(frame.attempts) == 3
    assert [a["backend"] for a in frame.attempts] == ["gdi", "wgc", "printwindow"]


def test_capturer_all_blank_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import edm.capture.select as sel

    win = _make_window(hwnd=101)
    monkeypatch.setattr(sel, "resolve_window", lambda _q: (win, []))
    monkeypatch.setattr(sel, "visible_fraction", lambda *_args, **_kwargs: 1.0)
    monkeypatch.setattr(sel, "root_window_at", lambda _p: 101)

    gdi = _StubBackend("gdi", image=_blank_image())
    wgc = _StubBackend("wgc", image=_blank_image())
    pw = _StubBackend("printwindow", image=_blank_image())

    capturer = Capturer({"gdi": gdi, "wgc": wgc, "printwindow": pw}, Config())
    with pytest.raises(EdmError) as exc_info:
        capturer.capture(CaptureTarget(kind="window", query="Mock"))
    assert exc_info.value.code == ErrorCode.CAPTURE_BLANK
    assert len(exc_info.value.details["attempts"]) == 3


def test_capturer_minimized_requires_restore(monkeypatch: pytest.MonkeyPatch) -> None:
    import edm.capture.select as sel

    min_win = _make_window(hwnd=101, minimized=True)
    restored_win = _make_window(hwnd=101, minimized=False)
    monkeypatch.setattr(sel, "resolve_window", lambda _q: (min_win, []))
    monkeypatch.setattr(sel, "window_info", lambda _hwnd: restored_win)
    monkeypatch.setattr(sel, "visible_fraction", lambda *_args, **_kwargs: 1.0)
    monkeypatch.setattr(sel, "root_window_at", lambda _p: 101)

    restore_calls: list[int] = []
    monkeypatch.setattr(sel, "_restore_window", lambda hwnd: restore_calls.append(hwnd))

    gdi = _StubBackend("gdi", image=_good_image())
    capturer = Capturer({"gdi": gdi}, Config())

    with pytest.raises(EdmError) as exc_info:
        capturer.capture(CaptureTarget(kind="window", query="Mock"), restore=False)
    assert exc_info.value.code == ErrorCode.WINDOW_MINIMIZED
    assert restore_calls == []

    frame, win = capturer.capture(CaptureTarget(kind="window", query="Mock"), restore=True)
    assert restore_calls == [101]
    assert win == restored_win
    assert frame.backend == "gdi"
