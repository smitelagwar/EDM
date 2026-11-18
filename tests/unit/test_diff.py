from PIL import Image, ImageDraw

from edm.geometry import Rect
from edm.observe.diff import diff_images, patch_diff


def test_patch_diff_identical_zero() -> None:
    a = Image.new("RGB", (24, 24), (100, 120, 140))
    b = Image.new("RGB", (24, 24), (100, 120, 140))
    assert patch_diff(a, b) == 0.0


def test_diff_bbox() -> None:
    a = Image.new("RGB", (100, 100), (0, 0, 0))
    b = Image.new("RGB", (100, 100), (0, 0, 0))
    draw = ImageDraw.Draw(b)
    draw.rectangle((20, 30, 39, 49), fill=(255, 255, 255))

    res = diff_images(a, b, pixel_threshold=24)
    assert res.bbox == Rect(20, 30, 40, 50)
    assert abs(res.changed_fraction - 0.04) < 1e-6
