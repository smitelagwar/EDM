"""Keyboard chord parsing and SendInput event generation."""

from __future__ import annotations

import ctypes
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from edm.errors import EdmError, ErrorCode
from edm.win32.api import user32

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

VK_TAB = 0x09
VK_RETURN = 0x0D

_VkKeyScanW = user32.VkKeyScanW
_VkKeyScanW.argtypes = [ctypes.c_wchar]
_VkKeyScanW.restype = ctypes.c_short

_KEY_NAMES: dict[str, int] = {
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "win": 0x5B,
    "super": 0x5B,
    "enter": VK_RETURN,
    "return": VK_RETURN,
    "esc": 0x1B,
    "escape": 0x1B,
    "tab": VK_TAB,
    "space": 0x20,
    "backspace": 0x08,
    "bs": 0x08,
    "delete": 0x2E,
    "del": 0x2E,
    "insert": 0x2D,
    "ins": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pgup": 0x21,
    "pagedown": 0x22,
    "pgdn": 0x22,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "printscreen": 0x2C,
    "prtsc": 0x2C,
    "apps": 0x5D,
    "capslock": 0x14,
    "volumemute": 0xAD,
    "volumedown": 0xAE,
    "volumeup": 0xAF,
    "mediaplaypause": 0xB3,
    **{f"f{i}": 0x6F + i for i in range(1, 25)},
}

_EXTENDED_VKS: frozenset[int] = frozenset(
    {
        0x21,  # pageup
        0x22,  # pagedown
        0x23,  # end
        0x24,  # home
        0x25,  # left
        0x26,  # up
        0x27,  # right
        0x28,  # down
        0x2C,  # printscreen
        0x2D,  # insert
        0x2E,  # delete
        0x5B,  # lwin
        0x5C,  # rwin
        0x5D,  # apps
        0x6F,  # numpad divide
        0x90,  # numlock
        0xA3,  # rcontrol
        0xA5,  # rmenu
    }
)


@dataclass(frozen=True)
class KeyEvent:
    """Low-level keyboard event ready for ``SendInput``."""

    vk: int
    scan: int
    flags: int


def default_vk_scan(ch: str) -> int:
    """Look up the virtual-key code for *ch* in the active keyboard layout."""
    if len(ch) != 1:
        return -1
    return int(_VkKeyScanW(ch))


def parse_chord(
    chord: str,
    vk_scan: Callable[[str], int] = default_vk_scan,
) -> list[int]:
    """Parse a key chord string such as ``'ctrl+shift+s'`` into virtual-key codes."""
    stripped = chord.strip()
    if not stripped:
        raise EdmError(ErrorCode.INVALID_ARGUMENT, "Key chord must not be empty.")

    parts = [p.strip() for p in stripped.split("+")]
    if any(not p for p in parts):
        raise EdmError(
            ErrorCode.INVALID_ARGUMENT,
            f"Malformed key chord: {chord!r}",
            details={"chord": chord},
        )

    vks: list[int] = []
    for part in parts:
        vk = _KEY_NAMES.get(part.lower())
        if vk is not None:
            vks.append(vk)
            continue
        if len(part) == 1:
            scanned = vk_scan(part)
            if scanned == -1 or (scanned & 0xFFFF) == 0xFFFF:
                raise EdmError(
                    ErrorCode.INVALID_ARGUMENT,
                    f"Character {part!r} has no virtual-key mapping in active layout.",
                    details={"key": part, "chord": chord},
                )
            vks.append(scanned & 0xFF)
            continue
        raise EdmError(
            ErrorCode.INVALID_ARGUMENT,
            f"Unknown key name {part!r} in chord {chord!r}.",
            details={"key": part, "chord": chord},
        )
    return vks


def key_state_events(vk: int, action: Literal["down", "up"]) -> list[KeyEvent]:
    """Build a single key-down or key-up event for *vk*."""
    if action not in ("down", "up"):
        raise EdmError(
            ErrorCode.INVALID_ARGUMENT,
            f"Invalid key action: {action!r}",
            details={"action": action},
        )
    flags = KEYEVENTF_EXTENDEDKEY if vk in _EXTENDED_VKS else 0
    if action == "up":
        flags |= KEYEVENTF_KEYUP
    return [KeyEvent(vk=vk, scan=0, flags=flags)]


def chord_events(vks: list[int]) -> list[KeyEvent]:
    """Generate press events in forward order followed by releases in reverse order."""
    if not vks:
        raise EdmError(ErrorCode.INVALID_ARGUMENT, "Chord virtual-key list must not be empty.")
    events: list[KeyEvent] = []
    for vk in vks:
        events.extend(key_state_events(vk, "down"))
    for vk in reversed(vks):
        events.extend(key_state_events(vk, "up"))
    return events


def unicode_events(text: str) -> list[KeyEvent]:
    """Generate ``KEYEVENTF_UNICODE`` events (and Enter/Tab VKs) for arbitrary text."""
    normalized = text.replace("\r\n", "\n")
    events: list[KeyEvent] = []
    for ch in normalized:
        if ch == "\n":
            events.append(KeyEvent(vk=VK_RETURN, scan=0, flags=0))
            events.append(KeyEvent(vk=VK_RETURN, scan=0, flags=KEYEVENTF_KEYUP))
        elif ch == "\t":
            events.append(KeyEvent(vk=VK_TAB, scan=0, flags=0))
            events.append(KeyEvent(vk=VK_TAB, scan=0, flags=KEYEVENTF_KEYUP))
        else:
            raw = ch.encode("utf-16-le")
            for idx in range(0, len(raw), 2):
                unit = int.from_bytes(raw[idx : idx + 2], "little")
                events.append(KeyEvent(vk=0, scan=unit, flags=KEYEVENTF_UNICODE))
                events.append(KeyEvent(vk=0, scan=unit, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
    return events
