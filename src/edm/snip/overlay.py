"""Fullscreen borderless Tk overlay for user-drawn region selection."""

from __future__ import annotations

import contextlib
import tkinter as tk
from typing import Any

from PIL import Image, ImageEnhance, ImageTk

from edm.geometry import Point, Rect
from edm.win32.dpi import ensure_dpi_awareness


def normalize_drag(p1: Point, p2: Point, min_size: int = 4) -> Rect | None:
    """Normalize any-direction drag endpoints into a Rect, or None if smaller than min_size."""
    left = min(p1.x, p2.x)
    top = min(p1.y, p2.y)
    right = max(p1.x, p2.x)
    bottom = max(p1.y, p2.y)
    if right - left < min_size or bottom - top < min_size:
        return None
    return Rect(left, top, right, bottom)


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def run_snip(
    frozen: Image.Image,
    virtual: Rect,
    prompt: str | None = None,
    timeout_s: float = 120.0,
) -> Rect | None:
    """Show a dimmed fullscreen overlay of `frozen` and return the dragged virtual-screen Rect."""
    ensure_dpi_awareness()
    if timeout_s <= 0:
        return None

    dimmed = ImageEnhance.Brightness(frozen).enhance(0.45)

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.geometry(f"{virtual.width}x{virtual.height}+{virtual.left}+{virtual.top}")

    canvas = tk.Canvas(
        root,
        width=virtual.width,
        height=virtual.height,
        highlightthickness=0,
        cursor="crosshair",
    )
    canvas.pack(fill="both", expand=True)

    bg_photo = ImageTk.PhotoImage(dimmed)
    canvas.create_image(0, 0, anchor="nw", image=bg_photo)

    if prompt:
        cx = virtual.width // 2
        pad_x = max(120, min(virtual.width // 2 - 20, len(prompt) * 5 + 24))
        canvas.create_rectangle(
            cx - pad_x,
            12,
            cx + pad_x,
            46,
            fill="#111827",
            outline="#00e5ff",
            width=1,
            tags="prompt",
        )
        canvas.create_text(
            cx,
            29,
            text=prompt,
            fill="#ffffff",
            font=("Segoe UI", 12, "bold"),
            tags="prompt",
        )

    start_local: tuple[int, int] | None = None
    result: Rect | None = None
    sel_photo: ImageTk.PhotoImage | None = None
    after_id: str | None = None
    closed = False

    def close() -> None:
        nonlocal after_id, closed
        if closed:
            return
        closed = True
        if after_id is not None:
            with contextlib.suppress(tk.TclError):
                root.after_cancel(after_id)
            after_id = None
        with contextlib.suppress(tk.TclError):
            root.destroy()

    def on_press(event: Any) -> None:
        nonlocal start_local
        start_local = (
            _clamp(int(event.x), 0, virtual.width),
            _clamp(int(event.y), 0, virtual.height),
        )
        canvas.delete("sel")

    def on_motion(event: Any) -> None:
        nonlocal sel_photo
        if start_local is None:
            return
        cur_x = _clamp(int(event.x), 0, virtual.width)
        cur_y = _clamp(int(event.y), 0, virtual.height)
        x0 = min(start_local[0], cur_x)
        y0 = min(start_local[1], cur_y)
        x1 = max(start_local[0], cur_x)
        y1 = max(start_local[1], cur_y)
        canvas.delete("sel")
        if x1 > x0 and y1 > y0:
            crop = frozen.crop((x0, y0, x1, y1))
            sel_photo = ImageTk.PhotoImage(crop)
            canvas.create_image(x0, y0, anchor="nw", image=sel_photo, tags="sel")
            canvas.create_rectangle(x0, y0, x1, y1, outline="#00e5ff", width=2, tags="sel")

    def on_release(event: Any) -> None:
        nonlocal result
        if start_local is None:
            return
        cur_x = _clamp(int(event.x), 0, virtual.width)
        cur_y = _clamp(int(event.y), 0, virtual.height)
        p1 = Point(virtual.left + start_local[0], virtual.top + start_local[1])
        p2 = Point(virtual.left + cur_x, virtual.top + cur_y)
        result = normalize_drag(p1, p2)
        close()

    def on_escape(_event: Any = None) -> None:
        nonlocal result
        result = None
        close()

    def on_timeout() -> None:
        nonlocal after_id, result
        after_id = None
        result = None
        close()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_motion)
    canvas.bind("<ButtonRelease-1>", on_release)
    root.bind("<Escape>", on_escape)
    root.bind_all("<Escape>", on_escape)
    root.focus_force()

    after_id = root.after(max(1, int(timeout_s * 1000)), on_timeout)
    root.mainloop()
    return result
