from __future__ import annotations

import time
from collections.abc import Iterator

import pytest

from edm.errors import EdmError, ErrorCode
from edm.geometry import Rect
from edm.perception.uia import RawElement, _read_value, collect_elements


class _FakeProvider:
    def __init__(self, items: list[RawElement], delay_s: float = 0.0) -> None:
        self._items = items
        self._delay_s = delay_s

    def iter_elements(self, hwnd: int) -> Iterator[RawElement]:
        del hwnd
        for item in self._items:
            if self._delay_s > 0:
                time.sleep(self._delay_s)
            yield item


class _FailingProvider:
    def iter_elements(self, hwnd: int) -> Iterator[RawElement]:
        del hwnd
        raise OSError("COM 0x80040201")
        yield  # pragma: no cover


def test_filter_and_order() -> None:
    items = [
        RawElement("Bottom", "Button", Rect(50, 200, 150, 240), True, True, "b1"),
        RawElement("Invisible", "Button", Rect(10, 10, 100, 50), True, False, "b_inv"),
        RawElement("Zero", "Button", Rect(10, 10, 10, 50), True, True, "b_zero"),
        RawElement("Offscreen", "Button", Rect(-9000, -9000, -8900, -8950), True, True, "b_off"),
        RawElement("Label", "Text", Rect(10, 10, 100, 40), True, True, "lbl"),
        RawElement("TopRight", "Edit", Rect(200, 20, 300, 50), True, True, "e1", value="hi"),
        RawElement("TopLeft", "Button", Rect(20, 20, 100, 50), True, True, "b0"),
    ]
    elements, truncated = collect_elements(
        101,
        max_elements=150,
        timeout_s=2.0,
        provider=_FakeProvider(items),
        screen_bounds=Rect(0, 0, 1920, 1080),
    )
    assert truncated is False
    assert [e.name for e in elements] == ["TopLeft", "TopRight", "Bottom"]
    assert [e.mark for e in elements] == [1, 2, 3]
    assert elements[1].value == "hi"


def test_collect_elements_timeout_partial() -> None:
    items = [
        RawElement(
            f"Btn{i}", "Button", Rect(10, 10 + i * 30, 100, 35 + i * 30), True, True, f"b{i}"
        )
        for i in range(10)
    ]
    elements, truncated = collect_elements(
        101,
        max_elements=150,
        timeout_s=0.35,
        provider=_FakeProvider(items, delay_s=0.1),
        screen_bounds=Rect(0, 0, 1920, 1080),
    )
    assert truncated is True
    assert 2 <= len(elements) <= 4


def test_uia_unavailable_maps_error() -> None:
    with pytest.raises(EdmError) as exc_info:
        collect_elements(101, provider=_FailingProvider())
    assert exc_info.value.code == ErrorCode.UIA_UNAVAILABLE


def test_uia_nan_timeout_and_get_pattern() -> None:
    with pytest.raises(EdmError) as exc_info:
        collect_elements(101, timeout_s=float("nan"), provider=_FakeProvider([]))
    assert exc_info.value.code == ErrorCode.INVALID_ARGUMENT

    class _PatternVal:
        Value = "from-get-pattern"

    class _Ctrl:
        def GetPattern(self, pid: int) -> _PatternVal | None:
            return _PatternVal() if pid == 10002 else None

    assert _read_value(_Ctrl()) == "from-get-pattern"
