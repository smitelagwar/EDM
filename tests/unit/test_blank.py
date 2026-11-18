import random

from PIL import Image, ImageDraw

from edm.capture.base import is_blank


def test_is_blank_uniform() -> None:
    img = Image.new("RGB", (200, 200), (15, 15, 15))
    assert is_blank(img) is True


def test_is_blank_noise_false() -> None:
    rng = random.Random(42)
    img = Image.new("RGB", (100, 100))
    pixels = [
        (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255)) for _ in range(100 * 100)
    ]
    img.putdata(pixels)
    assert is_blank(img) is False


def test_is_blank_ui_like_false() -> None:
    img = Image.new("RGB", (400, 300), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 399, 9), fill=(0, 0, 0))
    assert is_blank(img) is False
