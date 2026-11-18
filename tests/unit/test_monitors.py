"""Unit tests for Win32 monitor enumeration and virtual screen bounds."""

from __future__ import annotations

from edm.win32.monitors import MonitorInfo, list_monitors, virtual_screen


def test_monitors_live_shape() -> None:
    monitors = list_monitors()
    assert len(monitors) >= 1
    assert all(isinstance(m, MonitorInfo) for m in monitors)

    primaries = [m for m in monitors if m.primary]
    assert len(primaries) == 1
    assert primaries[0].index == 0
    assert [m.index for m in monitors] == list(range(len(monitors)))

    vscreen = virtual_screen()
    assert vscreen.width > 0
    assert vscreen.height > 0
    for m in monitors:
        assert m.rect.width > 0
        assert m.rect.height > 0
        assert m.dpi >= 96
        assert m.scale > 0
        assert vscreen.left <= m.rect.left
        assert vscreen.top <= m.rect.top
        assert vscreen.right >= m.rect.right
        assert vscreen.bottom >= m.rect.bottom
