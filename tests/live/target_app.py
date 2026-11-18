"""Standalone Tkinter target application for live EDM acceptance tests."""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import json
import tkinter as tk
from pathlib import Path
from typing import Any


def _enable_pmv2() -> None:
    with contextlib.suppress(Exception):
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))


def main() -> int:
    """Launch the EDM Target test window."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()

    _enable_pmv2()
    log_path: Path = args.log
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def write_event(kind: str, **data: Any) -> None:
        record = {"event": kind, **data}
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    root = tk.Tk()
    root.title("EDM Target")
    root.geometry("800x600+100+100")
    root.resizable(False, False)

    # Top color-square strip with zero border/highlight so (40,40), (160,40), (280,40) are exact.
    color_canvas = tk.Canvas(
        root,
        width=800,
        height=140,
        bg="#f0f0f0",
        bd=0,
        highlightthickness=0,
    )
    color_canvas.place(x=0, y=0)
    color_canvas.create_rectangle(40, 40, 120, 120, fill="#ff0000", outline="")
    color_canvas.create_rectangle(160, 40, 240, 120, fill="#00ff00", outline="")
    color_canvas.create_rectangle(280, 40, 360, 120, fill="#0000ff", outline="")

    ok_btn = tk.Button(
        root,
        text="EDM-OK",
        command=lambda: write_event("button_click", name="EDM-OK"),
    )
    ok_btn.place(x=40, y=160)

    entry = tk.Entry(root, width=40)
    entry.place(x=150, y=165)

    label = tk.Label(root, text="Çalışma Ağı İğne Şüphe Öğün")
    label.place(x=40, y=210)

    draw_canvas = tk.Canvas(
        root,
        width=300,
        height=200,
        bg="#ffffff",
        bd=0,
        highlightthickness=1,
        highlightbackground="#333333",
    )
    draw_canvas.place(x=40, y=260)

    def _on_mouse(kind: str, ev: tk.Event[Any]) -> None:
        write_event(
            kind,
            x=ev.x,
            y=ev.y,
            x_root=ev.x_root,
            y_root=ev.y_root,
            num=getattr(ev, "num", 0),
            delta=getattr(ev, "delta", 0),
        )

    draw_canvas.bind("<ButtonPress>", lambda e: _on_mouse("mouse_down", e))
    draw_canvas.bind("<ButtonRelease>", lambda e: _on_mouse("mouse_up", e))
    draw_canvas.bind("<B1-Motion>", lambda e: _on_mouse("drag_motion", e))
    draw_canvas.bind("<Motion>", lambda e: _on_mouse("motion", e))
    draw_canvas.bind("<MouseWheel>", lambda e: _on_mouse("wheel", e))

    root.bind(
        "<KeyPress>",
        lambda e: write_event("key_press", keysym=e.keysym, char=e.char),
    )
    root.bind(
        "<KeyRelease>",
        lambda e: write_event("key_release", keysym=e.keysym, char=e.char),
    )

    root.update_idletasks()
    with contextlib.suppress(Exception):
        ctypes.windll.user32.SetWindowTextW(ok_btn.winfo_id(), "EDM-OK")
    write_event("ready")
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
