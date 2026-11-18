"""Window occlusion estimation via grid hit-testing."""

from __future__ import annotations

from collections.abc import Callable

from edm.geometry import Point, Rect


def visible_fraction(
    rect: Rect,
    owned: set[int],
    hit_test: Callable[[Point], int],
    grid: int = 7,
) -> float:
    """Estimate the visible fraction of *rect* using a ``grid x grid`` hit-test."""
    if rect.width <= 0 or rect.height <= 0 or grid <= 0 or not owned:
        return 0.0

    hits = 0
    total = grid * grid
    for row in range(grid):
        y = rect.top + int((row + 0.5) * rect.height / grid)
        for col in range(grid):
            x = rect.left + int((col + 0.5) * rect.width / grid)
            if hit_test(Point(x, y)) in owned:
                hits += 1
    return hits / total
