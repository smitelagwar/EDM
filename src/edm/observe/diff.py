"""Image difference and patch comparison helpers."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageChops, ImageStat

from edm.errors import EdmError, ErrorCode
from edm.geometry import Rect


@dataclass(frozen=True)
class DiffResult:
    """Summary of pixel differences between two equally sized images."""

    changed_fraction: float
    bbox: Rect | None


def patch_diff(a: Image.Image, b: Image.Image) -> float:
    """Return normalized mean absolute RGB difference in ``[0.0, 1.0]``."""
    if a.size != b.size:
        return 1.0
    if a.size[0] == 0 or a.size[1] == 0:
        return 0.0
    diff_img = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    means = ImageStat.Stat(diff_img).mean
    return float(sum(means) / (len(means) * 255.0))


def diff_images(a: Image.Image, b: Image.Image, pixel_threshold: int = 24) -> DiffResult:
    """Compute changed pixel fraction and bounding box between *a* and *b*."""
    if a.size != b.size:
        raise EdmError(
            ErrorCode.INVALID_ARGUMENT,
            f"diff_images requires matching sizes, got {a.size} vs {b.size}.",
            details={"a_size": list(a.size), "b_size": list(b.size)},
        )
    w, h = a.size
    if w == 0 or h == 0:
        return DiffResult(changed_fraction=0.0, bbox=None)

    diff_img = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    r, g, b_ch = diff_img.split()
    max_diff = ImageChops.lighter(ImageChops.lighter(r, g), b_ch)
    mask = max_diff.point(lambda v: 255 if v >= pixel_threshold else 0)
    bbox_tuple = mask.getbbox()
    if bbox_tuple is None:
        return DiffResult(changed_fraction=0.0, bbox=None)
    changed_pixels = mask.histogram()[255]
    return DiffResult(
        changed_fraction=changed_pixels / (w * h),
        bbox=Rect(*bbox_tuple),
    )
