import pytest

from edm.actions.keys import (
    KEYEVENTF_EXTENDEDKEY,
    KEYEVENTF_KEYUP,
    KEYEVENTF_UNICODE,
    VK_RETURN,
    VK_TAB,
    chord_events,
    key_state_events,
    parse_chord,
    unicode_events,
)
from edm.errors import EdmError, ErrorCode


def _ascii_scan(ch: str) -> int:
    if len(ch) == 1 and ch.isascii() and ch.isalpha():
        return ord(ch.upper())
    return -1


def test_parse_chord_basic() -> None:
    vks = parse_chord("ctrl+shift+s", vk_scan=_ascii_scan)
    assert vks == [0x11, 0x10, 0x53]


def test_parse_chord_win_r() -> None:
    vks = parse_chord("win+r", vk_scan=_ascii_scan)
    assert vks == [0x5B, 0x52]


def test_parse_chord_unknown() -> None:
    with pytest.raises(EdmError) as exc_info:
        parse_chord("ctrl+nonexistentkey", vk_scan=_ascii_scan)
    assert exc_info.value.code == ErrorCode.INVALID_ARGUMENT

    with pytest.raises(EdmError) as exc_info2:
        parse_chord("ctrl+😀", vk_scan=lambda _c: -1)
    assert exc_info2.value.code == ErrorCode.INVALID_ARGUMENT


def test_parse_chord_layout_letter() -> None:
    def tr_scan(ch: str) -> int:
        return 0xBA if ch == "ş" else _ascii_scan(ch)

    assert parse_chord("ctrl+ş", vk_scan=tr_scan) == [0x11, 0xBA]


def test_chord_release_reverse() -> None:
    events = chord_events([0x11, 0x2E])  # ctrl + delete (extended)
    assert len(events) == 4
    # Press in order
    assert events[0].vk == 0x11 and (events[0].flags & KEYEVENTF_KEYUP) == 0
    assert events[1].vk == 0x2E and (events[1].flags & KEYEVENTF_EXTENDEDKEY) != 0
    # Release in reverse order
    assert events[2].vk == 0x2E and (events[2].flags & KEYEVENTF_KEYUP) != 0
    assert events[3].vk == 0x11 and (events[3].flags & KEYEVENTF_KEYUP) != 0


def test_unicode_events_surrogates() -> None:
    events = unicode_events("ğ😀")
    assert len(events) == 6
    assert all((e.flags & KEYEVENTF_UNICODE) != 0 for e in events)
    assert events[0].scan == ord("ğ")
    assert events[1].flags & KEYEVENTF_KEYUP


def test_unicode_newline_tab() -> None:
    events = unicode_events("a\r\nb\tc")
    vks = [e.vk for e in events if e.vk != 0]
    assert vks == [VK_RETURN, VK_RETURN, VK_TAB, VK_TAB]


def test_key_state_events() -> None:
    down = key_state_events(0x2E, "down")
    up = key_state_events(0x2E, "up")
    assert len(down) == 1 and (down[0].flags & KEYEVENTF_EXTENDEDKEY) != 0
    assert len(up) == 1 and (up[0].flags & KEYEVENTF_KEYUP) != 0
