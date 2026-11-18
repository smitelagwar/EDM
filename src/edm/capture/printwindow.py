"""Win32 PrintWindow capture backend with ``PW_RENDERFULLCONTENT``."""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

from PIL import Image

from edm.capture.base import Frame
from edm.errors import EdmError, ErrorCode
from edm.geometry import Rect
from edm.win32.api import GetWindowRect, gdi32, user32
from edm.win32.windows import window_info

_PW_RENDERFULLCONTENT = 0x00000002
_BI_RGB = 0
_DIB_RGB_COLORS = 0


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", _BITMAPINFOHEADER),
        ("bmiColors", wintypes.DWORD * 3),
    ]


_GetDC = user32.GetDC
_GetDC.argtypes = [wintypes.HWND]
_GetDC.restype = wintypes.HDC

_ReleaseDC = user32.ReleaseDC
_ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
_ReleaseDC.restype = ctypes.c_int

_PrintWindow = user32.PrintWindow
_PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
_PrintWindow.restype = wintypes.BOOL

_CreateCompatibleDC = gdi32.CreateCompatibleDC
_CreateCompatibleDC.argtypes = [wintypes.HDC]
_CreateCompatibleDC.restype = wintypes.HDC

_DeleteDC = gdi32.DeleteDC
_DeleteDC.argtypes = [wintypes.HDC]
_DeleteDC.restype = wintypes.BOOL

_CreateCompatibleBitmap = gdi32.CreateCompatibleBitmap
_CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
_CreateCompatibleBitmap.restype = wintypes.HBITMAP

_SelectObject = gdi32.SelectObject
_SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
_SelectObject.restype = wintypes.HGDIOBJ

_DeleteObject = gdi32.DeleteObject
_DeleteObject.argtypes = [wintypes.HGDIOBJ]
_DeleteObject.restype = wintypes.BOOL

_GetDIBits = gdi32.GetDIBits
_GetDIBits.argtypes = [
    wintypes.HDC,
    wintypes.HBITMAP,
    wintypes.UINT,
    wintypes.UINT,
    ctypes.c_void_p,
    ctypes.POINTER(_BITMAPINFO),
    wintypes.UINT,
]
_GetDIBits.restype = ctypes.c_int


def _get_window_rect(hwnd: int, fallback: Rect) -> Rect:
    rc = wintypes.RECT()
    if GetWindowRect(hwnd, ctypes.byref(rc)):
        wr = Rect(int(rc.left), int(rc.top), int(rc.right), int(rc.bottom))
        if wr.width > 0 and wr.height > 0:
            return wr
    return fallback


class PrintWindowBackend:
    """Capture backend using ``user32.PrintWindow`` and ``GetDIBits``."""

    name: str = "printwindow"

    def available(self) -> tuple[bool, str]:
        """Report PrintWindow availability."""
        return True, "user32.PrintWindow"

    def capture_rect(self, rect: Rect) -> Frame:
        """PrintWindow targets windows rather than arbitrary screen rectangles."""
        raise EdmError(
            ErrorCode.CAPTURE_FAILED,
            "PrintWindowBackend only supports capture_window.",
            details={"backend": self.name, "rect": rect.as_list()},
        )

    def capture_window(self, hwnd: int) -> Frame:
        """Capture *hwnd* via ``PrintWindow(..., PW_RENDERFULLCONTENT)`` aligned to DWM bounds."""
        info = window_info(hwnd)
        if info.minimized:
            raise EdmError(
                ErrorCode.WINDOW_MINIMIZED,
                f"Window {hwnd} is minimized and cannot be captured.",
                details={"backend": self.name, "hwnd": hwnd},
            )
        if info.rect.width <= 0 or info.rect.height <= 0:
            raise EdmError(
                ErrorCode.CAPTURE_FAILED,
                f"Window {hwnd} has empty bounds: {info.rect}",
                details={"backend": self.name, "hwnd": hwnd},
            )

        wr = _get_window_rect(hwnd, info.rect)
        bw, bh = wr.width, wr.height

        hdc_screen = _GetDC(0)
        if not hdc_screen:
            raise EdmError(
                ErrorCode.CAPTURE_FAILED,
                "GetDC(0) failed.",
                details={"backend": self.name, "hwnd": hwnd},
            )
        hdc_mem = None
        hbm = None
        old_obj = None
        try:
            hdc_mem = _CreateCompatibleDC(hdc_screen)
            if not hdc_mem:
                raise EdmError(ErrorCode.CAPTURE_FAILED, "CreateCompatibleDC failed.")
            hbm = _CreateCompatibleBitmap(hdc_screen, bw, bh)
            if not hbm:
                raise EdmError(ErrorCode.CAPTURE_FAILED, "CreateCompatibleBitmap failed.")
            old_obj = _SelectObject(hdc_mem, hbm)

            if not _PrintWindow(hwnd, hdc_mem, _PW_RENDERFULLCONTENT):
                raise EdmError(
                    ErrorCode.CAPTURE_FAILED,
                    f"PrintWindow failed for hwnd={hwnd}",
                    details={"backend": self.name, "hwnd": hwnd},
                )

            bmi = _BITMAPINFO()
            bmi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
            bmi.bmiHeader.biWidth = bw
            bmi.bmiHeader.biHeight = -bh
            bmi.bmiHeader.biPlanes = 1
            bmi.bmiHeader.biBitCount = 32
            bmi.bmiHeader.biCompression = _BI_RGB

            buf = (ctypes.c_ubyte * (bw * bh * 4))()
            lines = _GetDIBits(
                hdc_mem,
                hbm,
                0,
                bh,
                ctypes.byref(buf),
                ctypes.byref(bmi),
                _DIB_RGB_COLORS,
            )
            if lines != bh:
                raise EdmError(
                    ErrorCode.CAPTURE_FAILED,
                    f"GetDIBits returned {lines} lines, expected {bh}",
                    details={"backend": self.name, "hwnd": hwnd},
                )
            img = Image.frombuffer("RGB", (bw, bh), bytes(buf), "raw", "BGRX", 0, 1).copy()
        finally:
            if hdc_mem and old_obj:
                _SelectObject(hdc_mem, old_obj)
            if hbm:
                _DeleteObject(hbm)
            if hdc_mem:
                _DeleteDC(hdc_mem)
            _ReleaseDC(0, hdc_screen)

        if wr != info.rect:
            left = max(0, min(bw, info.rect.left - wr.left))
            top = max(0, min(bh, info.rect.top - wr.top))
            right = max(left, min(bw, info.rect.right - wr.left))
            bottom = max(top, min(bh, info.rect.bottom - wr.top))
            if right > left and bottom > top:
                img = img.crop((left, top, right, bottom))

        return Frame(
            image=img,
            screen_rect=info.rect,
            backend=self.name,
            captured_at=time.time(),
            attempts=[{"backend": self.name, "ok": True}],
        )
