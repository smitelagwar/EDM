"""Unit tests for geometry primitives, fit_within, and ImageMapping."""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from edm.errors import EdmError, ErrorCode
from edm.geometry import ImageMapping, Point, Rect, fit_within


def test_rect_operations() -> None:
    r = Rect.from_xywh(10, 20, 100, 50)
    assert r == Rect(10, 20, 110, 70)
    assert r.width == 100
    assert r.height == 50
    assert r.center == Point(60, 45)
    assert r.as_list() == [10, 20, 110, 70]
    assert r.contains(Point(10, 20))
    assert r.contains(Point(109, 69))
    assert not r.contains(Point(110, 70))
    assert not r.contains(Point(9, 20))

    other = Rect(50, 30, 150, 80)
    assert r.intersection(other) == Rect(50, 30, 110, 70)
    assert r.intersection(Rect(110, 20, 200, 70)) is None


def test_fit_within() -> None:
    assert fit_within((2560, 1440), 1600) == (1600, 900)
    assert fit_within((800, 600), 1600) == (800, 600)
    assert fit_within((100, 4000), 1000) == (25, 1000)
    assert fit_within((10000, 1), 100) == (100, 1)


def test_mapping_identity() -> None:
    m = ImageMapping(Rect(0, 0, 2560, 1440), Rect(0, 0, 2560, 1440), (2560, 1440))
    assert m.scale == 1.0
    assert m.to_screen(100, 200) == Point(100, 200)
    assert m.from_screen(Point(100, 200)) == (100.0, 200.0)


def test_mapping_scaled() -> None:
    m = ImageMapping(Rect(0, 0, 2560, 1440), Rect(0, 0, 2560, 1440), (1600, 900))
    assert m.scale == pytest.approx(0.625)
    assert m.to_screen(800, 450) == Point(1280, 720)


def test_mapping_negative_origin() -> None:
    m = ImageMapping(Rect(-1920, 0, 0, 1080), Rect(0, 0, 1920, 1080), (1600, 900))
    assert m.to_screen(0, 0) == Point(-1920, 0)


def test_norm1000() -> None:
    m = ImageMapping(Rect(0, 0, 2560, 1440), Rect(0, 0, 2560, 1440), (1600, 900))
    assert m.to_screen(500, 500, "norm1000") == Point(1280, 720)
    assert m.to_screen(0, 0, "norm1000") == Point(0, 0)
    assert m.to_screen(1000, 1000, "norm1000") == Point(2559, 1439)


def test_child_zoom_chain() -> None:
    parent = ImageMapping(Rect(0, 0, 2560, 1440), Rect(0, 0, 2560, 1440), (1600, 900))
    child = parent.child(Rect.from_xywh(400, 225, 800, 450), (1600, 900))
    assert child.to_screen(800, 450) == Point(1280, 720)

    grandchild = child.child(Rect.from_xywh(400, 225, 800, 450), (1600, 900))
    assert grandchild.to_screen(800, 450) == Point(1280, 720)


def test_out_of_bounds_raises() -> None:
    m = ImageMapping(Rect(0, 0, 2560, 1440), Rect(0, 0, 2560, 1440), (1600, 900))
    with pytest.raises(EdmError) as exc_info:
        m.to_screen(1600, 450)
    assert exc_info.value.code == ErrorCode.POINT_OUT_OF_BOUNDS

    with pytest.raises(EdmError) as exc_info2:
        m.to_screen(-1, 0)
    assert exc_info2.value.code == ErrorCode.POINT_OUT_OF_BOUNDS

    with pytest.raises(EdmError) as exc_info3:
        m.to_screen(1001, 500, "norm1000")
    assert exc_info3.value.code == ErrorCode.POINT_OUT_OF_BOUNDS


@given(
    frame_x=st.integers(min_value=-3840, max_value=3840),
    frame_y=st.integers(min_value=-2160, max_value=2160),
    crop_x=st.integers(min_value=0, max_value=400),
    crop_y=st.integers(min_value=0, max_value=400),
    crop_w=st.integers(min_value=100, max_value=2000),
    crop_h=st.integers(min_value=100, max_value=2000),
    scale_num=st.integers(min_value=1, max_value=16),
    fx=st.floats(min_value=0.0, max_value=0.999, allow_nan=False, allow_infinity=False),
    fy=st.floats(min_value=0.0, max_value=0.999, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=150)
def test_mapping_roundtrip_scaled(
    frame_x: int,
    frame_y: int,
    crop_x: int,
    crop_y: int,
    crop_w: int,
    crop_h: int,
    scale_num: int,
    fx: float,
    fy: float,
) -> None:
    # Scale in [0.25, 4.0]
    scale = scale_num / 4.0
    img_w = max(1, round(crop_w * scale))
    img_h = max(1, round(crop_h * scale))
    frame = Rect.from_xywh(frame_x, frame_y, crop_x + crop_w + 50, crop_y + crop_h + 50)
    crop = Rect.from_xywh(crop_x, crop_y, crop_w, crop_h)
    mapping = ImageMapping(frame_rect=frame, crop=crop, image_size=(img_w, img_h))

    px = frame_x + crop_x + int(fx * crop_w)
    py = frame_y + crop_y + int(fy * crop_h)
    p = Point(px, py)

    ix, iy = mapping.from_screen(p)
    rt = mapping.to_screen(ix, iy)
    tol = math.ceil(1.0 / mapping.scale)
    assert abs(rt.x - p.x) <= tol
    assert abs(rt.y - p.y) <= tol
