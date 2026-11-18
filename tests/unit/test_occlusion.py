from edm.capture.occlusion import visible_fraction
from edm.geometry import Point, Rect


def test_visible_fraction_full() -> None:
    rect = Rect(0, 0, 700, 700)
    frac = visible_fraction(rect, {100}, lambda _p: 100, grid=7)
    assert frac == 1.0


def test_visible_fraction_half() -> None:
    rect = Rect(0, 0, 700, 700)

    def hit_test(p: Point) -> int:
        return 100 if p.x >= 350 else 200

    frac = visible_fraction(rect, {100}, hit_test, grid=7)
    assert 0.40 <= frac <= 0.60
