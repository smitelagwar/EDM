"""Unit tests for edm.observe.render."""

from __future__ import annotations

from PIL import Image

from edm.geometry import Rect
from edm.observe.render import (
    draw_cursor,
    draw_grid,
    draw_marks,
    encode_image,
    make_preview,
    zoom_crop,
)


def test_make_preview_downscales_without_upscaling() -> None:
    large = Image.new("RGB", (2560, 1440), (10, 20, 30))
    down = make_preview(large, 1600)
    assert down.size == (1600, 900)

    small = Image.new("RGB", (800, 600), (10, 20, 30))
    same = make_preview(small, 1600)
    assert same.size == (800, 600)
    assert same is not small


def test_draw_cursor_does_not_mutate_original() -> None:
    base = Image.new("RGB", (100, 100), (0, 0, 0))
    out = draw_cursor(base, (50.0, 50.0))
    assert out.size == (100, 100)
    assert base.getpixel((50, 50)) == (0, 0, 0)
    # Crosshair draws red near (50, 50)
    assert out.getpixel((50, 50)) != (0, 0, 0) or out.getpixel((54, 50)) != (0, 0, 0)


def test_grid_keeps_size() -> None:
    base = Image.new("RGB", (640, 480), (20, 20, 20))
    out = draw_grid(base, step=100)
    assert out.size == (640, 480)
    assert out is not base
    assert base.getpixel((100, 0)) == (20, 20, 20)
    assert out.getpixel((100, 0)) != (20, 20, 20)


def test_draw_marks_renders_boxes_without_mutation() -> None:
    base = Image.new("RGB", (200, 200), (30, 30, 30))
    out = draw_marks(base, [(1, Rect(20, 30, 80, 70)), (2, Rect(100, 100, 150, 140))])
    assert out.size == (200, 200)
    assert base.getpixel((20, 30)) == (30, 30, 30)
    assert out.getpixel((20, 30)) != (30, 30, 30)


def test_encode_respects_max_bytes() -> None:
    # 4K noisy image exceeds 1.5 MB as lossless PNG and fits under 1.5 MB as JPEG
    noisy = Image.effect_noise((3840, 2160), 12).convert("RGB")
    data, mime = encode_image(noisy, 1_500_000)
    assert len(data) <= 1_500_000
    assert mime == "image/jpeg"


def test_encode_small_uses_png() -> None:
    small = Image.new("RGB", (128, 128), (12, 34, 56))
    data, mime = encode_image(small, 1_500_000)
    assert len(data) <= 1_500_000
    assert mime == "image/png"


def test_zoom_crop_factor_cap() -> None:
    original = Image.new("RGB", (1000, 1000), (50, 50, 50))
    # 50x50 crop with max_edge=1600 -> capped at 4x = 200x200
    zoomed = zoom_crop(original, Rect(100, 100, 150, 150), max_edge=1600, factor=None)
    assert zoomed.size == (200, 200)

    # Explicit factor > 4 is also capped at 4x
    zoomed_explicit = zoom_crop(original, Rect(100, 100, 150, 150), max_edge=1600, factor=10.0)
    assert zoomed_explicit.size == (200, 200)

    # Explicit factor=2.0 -> 100x100
    zoomed_2x = zoom_crop(original, Rect(100, 100, 150, 150), max_edge=1600, factor=2.0)
    assert zoomed_2x.size == (100, 100)

    # max_edge smaller than 4x caps the output
    zoomed_edge = zoom_crop(original, Rect(100, 100, 150, 150), max_edge=150, factor=None)
    assert zoomed_edge.size == (150, 150)
