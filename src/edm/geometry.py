"""Coordinate geometry, preview scaling, and screen mapping primitives."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from edm.errors import EdmError, ErrorCode

CoordSpace = Literal["pixel", "norm1000"]


@dataclass(frozen=True)
class Point:
    """Integer point in screen or image coordinates."""

    x: int
    y: int


@dataclass(frozen=True)
class Rect:
    """Half-open integer rectangle [left, right) x [top, bottom)."""

    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        """Return rectangle width in pixels."""
        return self.right - self.left

    @property
    def height(self) -> int:
        """Return rectangle height in pixels."""
        return self.bottom - self.top

    @property
    def center(self) -> Point:
        """Return the integer center point of the rectangle."""
        return Point(self.left + self.width // 2, self.top + self.height // 2)

    def contains(self, p: Point) -> bool:
        """Return True if point p lies within [left, right) x [top, bottom)."""
        return self.left <= p.x < self.right and self.top <= p.y < self.bottom

    def intersection(self, other: Rect) -> Rect | None:
        """Return the non-empty intersection with another rectangle, or None."""
        left = max(self.left, other.left)
        top = max(self.top, other.top)
        right = min(self.right, other.right)
        bottom = min(self.bottom, other.bottom)
        if right <= left or bottom <= top:
            return None
        return Rect(left, top, right, bottom)

    @classmethod
    def from_xywh(cls, x: int, y: int, w: int, h: int) -> Rect:
        """Construct a Rect from origin (x, y) and dimensions (w, h)."""
        return cls(x, y, x + w, y + h)

    def as_list(self) -> list[int]:
        """Return [left, top, right, bottom] as a JSON-friendly list."""
        return [self.left, self.top, self.right, self.bottom]


def fit_within(size: tuple[int, int], max_edge: int) -> tuple[int, int]:
    """Scale (w, h) down so max(w, h) <= max_edge, preserving aspect ratio without upscaling."""
    w, h = size
    if w <= 0 or h <= 0 or max_edge <= 0:
        raise EdmError(
            ErrorCode.INVALID_ARGUMENT,
            f"fit_within requires positive dimensions and max_edge, got {size}, {max_edge}",
        )
    longest = max(w, h)
    if longest <= max_edge:
        return (w, h)
    if w >= h:
        new_w = max_edge
        new_h = max(1, min(max_edge, math.floor(h * max_edge / w + 0.5)))
    else:
        new_h = max_edge
        new_w = max(1, min(max_edge, math.floor(w * max_edge / h + 0.5)))
    return (new_w, new_h)


@dataclass(frozen=True)
class ImageMapping:
    """Bidirectional mapping between preview/zoom image coordinates and physical screen pixels.

    `frame_rect` is the captured frame's physical screen rectangle.
    `crop` is the active sub-region in frame-local pixels.
    `image_size` is the (width, height) of the image presented to the agent.
    """

    frame_rect: Rect
    crop: Rect
    image_size: tuple[int, int]

    @property
    def scale(self) -> float:
        """Return image-to-crop horizontal scale factor (image_w / crop_w)."""
        if self.crop.width <= 0:
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"ImageMapping crop width must be positive, got {self.crop.width}",
            )
        return self.image_size[0] / self.crop.width

    def to_screen(self, x: float, y: float, space: CoordSpace = "pixel") -> Point:
        """Map image coordinates (x, y) in `space` to a physical screen Point."""
        img_w, img_h = self.image_size
        if img_w <= 0 or img_h <= 0 or self.crop.width <= 0 or self.crop.height <= 0:
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                "ImageMapping dimensions and crop must be positive.",
            )
        if not (math.isfinite(x) and math.isfinite(y)):
            raise EdmError(
                ErrorCode.POINT_OUT_OF_BOUNDS,
                f"Coordinates must be finite, got ({x}, {y}).",
            )

        if space == "pixel":
            if x < 0 or x >= img_w or y < 0 or y >= img_h:
                raise EdmError(
                    ErrorCode.POINT_OUT_OF_BOUNDS,
                    f"Pixel ({x}, {y}) is outside image bounds {img_w}x{img_h}.",
                )
            px = x
            py = y
        elif space == "norm1000":
            if x < 0 or x > 1000 or y < 0 or y > 1000:
                raise EdmError(
                    ErrorCode.POINT_OUT_OF_BOUNDS,
                    f"Normalized coordinates ({x}, {y}) must be within [0, 1000].",
                )
            px = (x / 1000.0) * img_w
            py = (y / 1000.0) * img_h
        else:
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"Unsupported coord_space: {space!r}",
            )

        sx_f = self.frame_rect.left + self.crop.left + px * (self.crop.width / img_w)
        sy_f = self.frame_rect.top + self.crop.top + py * (self.crop.height / img_h)
        sx = math.floor(sx_f + 0.5)
        sy = math.floor(sy_f + 0.5)

        min_x = self.frame_rect.left + self.crop.left
        max_x = self.frame_rect.left + self.crop.right - 1
        min_y = self.frame_rect.top + self.crop.top
        max_y = self.frame_rect.top + self.crop.bottom - 1
        sx = max(min_x, min(max_x, sx))
        sy = max(min_y, min(max_y, sy))
        return Point(sx, sy)

    def from_screen(self, p: Point) -> tuple[float, float]:
        """Map a physical screen Point back to floating-point image pixel coordinates."""
        img_w, img_h = self.image_size
        if self.crop.width <= 0 or self.crop.height <= 0:
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                "ImageMapping crop dimensions must be positive.",
            )
        px = (p.x - self.frame_rect.left - self.crop.left) * (img_w / self.crop.width)
        py = (p.y - self.frame_rect.top - self.crop.top) * (img_h / self.crop.height)
        return (px, py)

    def child(self, crop_in_image: Rect, image_size: tuple[int, int]) -> ImageMapping:
        """Create a child ImageMapping for a zoom crop specified in this image's pixel space."""
        img_w, img_h = self.image_size
        if crop_in_image.width <= 0 or crop_in_image.height <= 0:
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"Zoom crop must have positive size, got {crop_in_image}.",
            )
        if (
            crop_in_image.left < 0
            or crop_in_image.top < 0
            or crop_in_image.right > img_w
            or crop_in_image.bottom > img_h
        ):
            raise EdmError(
                ErrorCode.POINT_OUT_OF_BOUNDS,
                f"Zoom crop {crop_in_image} exceeds image bounds {img_w}x{img_h}.",
            )

        inv_x = self.crop.width / img_w
        inv_y = self.crop.height / img_h
        new_crop = Rect(
            left=self.crop.left + math.floor(crop_in_image.left * inv_x + 0.5),
            top=self.crop.top + math.floor(crop_in_image.top * inv_y + 0.5),
            right=self.crop.left + math.floor(crop_in_image.right * inv_x + 0.5),
            bottom=self.crop.top + math.floor(crop_in_image.bottom * inv_y + 0.5),
        )
        return ImageMapping(
            frame_rect=self.frame_rect,
            crop=new_crop,
            image_size=image_size,
        )
