"""Win32 ``SendInput`` sink and ``InputSink`` protocol."""

from __future__ import annotations

import ctypes
from collections.abc import Sequence
from ctypes import wintypes
from typing import Protocol

from edm.actions.keys import KEYEVENTF_KEYUP, KEYEVENTF_UNICODE, KeyEvent, key_state_events
from edm.actions.mouse import (
    MOUSEEVENTF_ABSOLUTE,
    MOUSEEVENTF_LEFTDOWN,
    MOUSEEVENTF_LEFTUP,
    MOUSEEVENTF_MIDDLEDOWN,
    MOUSEEVENTF_MIDDLEUP,
    MOUSEEVENTF_MOVE,
    MOUSEEVENTF_RIGHTDOWN,
    MOUSEEVENTF_RIGHTUP,
    MOUSEEVENTF_VIRTUALDESK,
    MouseEvent,
    mouse_button_events,
    normalize_abs,
)
from edm.errors import EdmError, ErrorCode
from edm.geometry import Point
from edm.win32.api import SendInput, user32
from edm.win32.monitors import virtual_screen

_INPUT_MOUSE = 0
_INPUT_KEYBOARD = 1

_GetCursorPos = user32.GetCursorPos
_GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
_GetCursorPos.restype = wintypes.BOOL

_SetCursorPos = user32.SetCursorPos
_SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
_SetCursorPos.restype = wintypes.BOOL


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", _MOUSEINPUT),
        ("ki", _KEYBDINPUT),
        ("hi", _HARDWAREINPUT),
    ]


class _INPUT(ctypes.Structure):
    _anonymous_ = ("union",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", _INPUT_UNION),
    ]


class InputSink(Protocol):
    """Protocol for desktop input injection backends."""

    def send(self, events: Sequence[KeyEvent | MouseEvent]) -> int:
        """Send a sequence of key/mouse events and return the delivered count."""
        ...

    def move_to(self, p: Point) -> None:
        """Move the cursor to physical screen point *p*."""
        ...

    def cursor_pos(self) -> Point:
        """Return the current physical cursor position."""
        ...

    def release_held(self) -> None:
        """Release any keys or mouse buttons left pressed by this sink."""
        ...


class Win32InputSink:
    """``SendInput``-based input sink with held-state tracking."""

    def __init__(self) -> None:
        self._held_vks: set[int] = set()
        self._held_buttons: set[str] = set()

    def _track_event(self, ev: KeyEvent | MouseEvent) -> None:
        if isinstance(ev, KeyEvent):
            if (ev.flags & KEYEVENTF_UNICODE) == 0 and ev.vk != 0:
                if ev.flags & KEYEVENTF_KEYUP:
                    self._held_vks.discard(ev.vk)
                else:
                    self._held_vks.add(ev.vk)
        else:
            if ev.flags & MOUSEEVENTF_LEFTDOWN:
                self._held_buttons.add("left")
            if ev.flags & MOUSEEVENTF_LEFTUP:
                self._held_buttons.discard("left")
            if ev.flags & MOUSEEVENTF_RIGHTDOWN:
                self._held_buttons.add("right")
            if ev.flags & MOUSEEVENTF_RIGHTUP:
                self._held_buttons.discard("right")
            if ev.flags & MOUSEEVENTF_MIDDLEDOWN:
                self._held_buttons.add("middle")
            if ev.flags & MOUSEEVENTF_MIDDLEUP:
                self._held_buttons.discard("middle")

    def send(self, events: Sequence[KeyEvent | MouseEvent]) -> int:
        """Deliver *events* via ``SendInput``; raise ``INPUT_BLOCKED`` on partial send."""
        n = len(events)
        if n == 0:
            return 0
        arr = (_INPUT * n)()
        for idx, ev in enumerate(events):
            if isinstance(ev, KeyEvent):
                arr[idx].type = _INPUT_KEYBOARD
                arr[idx].ki = _KEYBDINPUT(
                    wVk=ev.vk,
                    wScan=ev.scan,
                    dwFlags=ev.flags,
                    time=0,
                    dwExtraInfo=0,
                )
            else:
                arr[idx].type = _INPUT_MOUSE
                arr[idx].mi = _MOUSEINPUT(
                    dx=ev.dx,
                    dy=ev.dy,
                    mouseData=ctypes.c_uint32(ev.data).value,
                    dwFlags=ev.flags,
                    time=0,
                    dwExtraInfo=0,
                )
            self._track_event(ev)

        sent = int(SendInput(n, ctypes.byref(arr), ctypes.sizeof(_INPUT)))
        if sent < n:
            raise EdmError(
                ErrorCode.INPUT_BLOCKED,
                f"SendInput delivered {sent} of {n} events.",
                details={"sent": sent, "expected": n, "win32_error": ctypes.get_last_error()},
            )
        return sent

    def move_to(self, p: Point) -> None:
        """Move the cursor to *p* using normalized virtual-desktop coordinates."""
        nx, ny = normalize_abs(p, virtual_screen())
        self.send(
            [
                MouseEvent(
                    flags=MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK,
                    dx=nx,
                    dy=ny,
                )
            ]
        )
        cur = self.cursor_pos()
        if abs(cur.x - p.x) >= 1 or abs(cur.y - p.y) >= 1:
            _SetCursorPos(p.x, p.y)

    def cursor_pos(self) -> Point:
        """Return the current physical cursor position."""
        pt = wintypes.POINT()
        _GetCursorPos(ctypes.byref(pt))
        return Point(int(pt.x), int(pt.y))

    def release_held(self) -> None:
        """Release all keys and mouse buttons currently tracked as held."""
        cleanup: list[KeyEvent | MouseEvent] = []
        for btn in list(self._held_buttons):
            cleanup.extend(mouse_button_events(btn, "up"))
        for vk in list(self._held_vks):
            cleanup.extend(key_state_events(vk, "up"))
        self._held_buttons.clear()
        self._held_vks.clear()
        if cleanup:
            self.send(cleanup)
