"""Win32 clipboard text and DIB image helpers with retry and handle cleanup."""

from __future__ import annotations

import ctypes
import struct
import time
from ctypes import wintypes
from io import BytesIO

from PIL import Image

from edm.errors import EdmError, ErrorCode
from edm.win32.api import kernel32, user32

_CF_DIB = 8
_CF_UNICODETEXT = 13
_GMEM_MOVEABLE = 0x0002

_OpenClipboard = user32.OpenClipboard
_OpenClipboard.argtypes = [wintypes.HWND]
_OpenClipboard.restype = wintypes.BOOL

_CloseClipboard = user32.CloseClipboard
_CloseClipboard.argtypes = []
_CloseClipboard.restype = wintypes.BOOL

_EmptyClipboard = user32.EmptyClipboard
_EmptyClipboard.argtypes = []
_EmptyClipboard.restype = wintypes.BOOL

_IsClipboardFormatAvailable = user32.IsClipboardFormatAvailable
_IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
_IsClipboardFormatAvailable.restype = wintypes.BOOL

_GetClipboardData = user32.GetClipboardData
_GetClipboardData.argtypes = [wintypes.UINT]
_GetClipboardData.restype = wintypes.HANDLE

_SetClipboardData = user32.SetClipboardData
_SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
_SetClipboardData.restype = wintypes.HANDLE

_GlobalAlloc = kernel32.GlobalAlloc
_GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
_GlobalAlloc.restype = wintypes.HGLOBAL

_GlobalFree = kernel32.GlobalFree
_GlobalFree.argtypes = [wintypes.HGLOBAL]
_GlobalFree.restype = wintypes.HGLOBAL

_GlobalLock = kernel32.GlobalLock
_GlobalLock.argtypes = [wintypes.HGLOBAL]
_GlobalLock.restype = ctypes.c_void_p

_GlobalUnlock = kernel32.GlobalUnlock
_GlobalUnlock.argtypes = [wintypes.HGLOBAL]
_GlobalUnlock.restype = wintypes.BOOL

_GlobalSize = kernel32.GlobalSize
_GlobalSize.argtypes = [wintypes.HGLOBAL]
_GlobalSize.restype = ctypes.c_size_t


def _open_clipboard_with_retry() -> None:
    for attempt in range(10):
        if _OpenClipboard(0):
            return
        if attempt < 9:
            time.sleep(0.05)
    raise EdmError(ErrorCode.BUSY, "Clipboard is locked by another process.")


def get_text() -> str | None:
    """Return Unicode text currently on the clipboard, or None."""
    _open_clipboard_with_retry()
    try:
        if not _IsClipboardFormatAvailable(_CF_UNICODETEXT):
            return None
        handle = _GetClipboardData(_CF_UNICODETEXT)
        if not handle:
            return None
        ptr = _GlobalLock(handle)
        if not ptr:
            return None
        try:
            return ctypes.wstring_at(ptr)
        finally:
            _GlobalUnlock(handle)
    finally:
        _CloseClipboard()


def set_text(s: str) -> None:
    """Copy Unicode text *s* onto the Windows clipboard."""
    raw = (s + "\0").encode("utf-16-le")
    hmem = _GlobalAlloc(_GMEM_MOVEABLE, len(raw))
    if not hmem:
        raise EdmError(ErrorCode.INTERNAL, "GlobalAlloc failed for clipboard text.")
    ptr = _GlobalLock(hmem)
    if not ptr:
        _GlobalFree(hmem)
        raise EdmError(ErrorCode.INTERNAL, "GlobalLock failed for clipboard text.")
    try:
        ctypes.memmove(ptr, raw, len(raw))
    finally:
        _GlobalUnlock(hmem)

    _open_clipboard_with_retry()
    try:
        _EmptyClipboard()
        if not _SetClipboardData(_CF_UNICODETEXT, hmem):
            _GlobalFree(hmem)
            raise EdmError(ErrorCode.INTERNAL, "SetClipboardData failed.")
    finally:
        _CloseClipboard()


def get_image() -> Image.Image | None:
    """Return an RGB ``PIL.Image`` from ``CF_DIB`` on the clipboard, or None."""
    _open_clipboard_with_retry()
    try:
        if not _IsClipboardFormatAvailable(_CF_DIB):
            return None
        handle = _GetClipboardData(_CF_DIB)
        if not handle:
            return None
        size = int(_GlobalSize(handle))
        ptr = _GlobalLock(handle)
        if not ptr or size < 40:
            if ptr:
                _GlobalUnlock(handle)
            return None
        try:
            dib = ctypes.string_at(ptr, size)
        finally:
            _GlobalUnlock(handle)
    finally:
        _CloseClipboard()

    header_size = struct.unpack_from("<I", dib, 0)[0]
    bit_count = struct.unpack_from("<H", dib, 14)[0]
    clr_used = struct.unpack_from("<I", dib, 32)[0]
    palette_entries = clr_used if clr_used else (1 << bit_count if bit_count <= 8 else 0)
    offset = 14 + header_size + palette_entries * 4
    bmp_header = struct.pack("<2sIHHI", b"BM", 14 + len(dib), 0, 0, offset)
    with Image.open(BytesIO(bmp_header + dib)) as img:
        return img.convert("RGB")
