"""Preview scaling, annotation overlays, zoom cropping, and image encoding."""

from __future__ import annotations

import math
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from edm.errors import EdmError, ErrorCode
from edm.geometry import Rect, fit_within

_JPEG_QUALITIES: tuple[int, ...] = (85, 75, 60)
_MAX_ZOOM_FACTOR = 4.0
_MARK_PALETTE: tuple[tuple[int, int, int], ...] = (
    (255, 196, 0),
    (0, 210, 255),
    (255, 80, 160),
    (120, 255, 80),
)


def _ensure_rgb_copy(img: Image.Image) -> Image.Image:
    if img.mode == "RGB":
        return img.copy()
    return img.convert("RGB")


def make_preview(img: Image.Image, max_edge: int) -> Image.Image:
    """Scale *img* down using Lanczos so its longest edge is at most *max_edge*."""
    target_size = fit_within(img.size, max_edge)
    if target_size == img.size:
        return img.copy()
    return img.resize(target_size, Image.Resampling.LANCZOS)


def draw_cursor(img: Image.Image, xy: tuple[float, float]) -> Image.Image:
    """Return a copy of *img* with a red crosshair drawn at *xy*."""
    out = _ensure_rgb_copy(img)
    draw = ImageDraw.Draw(out)
    cx = round(xy[0])
    cy = round(xy[1])
    arm = 12
    red = (255, 0, 0)
    white = (255, 255, 255)

    draw.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), outline=white, width=1)
    draw.line((cx - arm, cy, cx + arm, cy), fill=red, width=2)
    draw.line((cx, cy - arm, cx, cy + arm), fill=red, width=2)
    draw.ellipse((cx - 2, cy - 2, cx + 2, cy + 2), fill=red)
    return out


def draw_grid(img: Image.Image, step: int = 100) -> Image.Image:
    """Return a copy of *img* with labeled edge ticks every *step* pixels."""
    if step <= 0:
        raise EdmError(
            ErrorCode.INVALID_ARGUMENT,
            f"Grid step must be positive, got {step}.",
            details={"step": step},
        )
    out = _ensure_rgb_copy(img)
    w, h = out.size
    draw = ImageDraw.Draw(out)
    font = ImageFont.load_default()
    tick_len = 8
    fg = (255, 255, 0)
    bg = (0, 0, 0)

    for x in range(step, w, step):
        draw.line((x, 0, x, tick_len), fill=fg, width=1)
        draw.line((x, max(0, h - tick_len - 1), x, h - 1), fill=fg, width=1)
        label = str(x)
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        lx = min(max(0, x + 2), max(0, w - tw - 2))
        draw.rectangle((lx, 2, lx + tw + 2, 2 + th + 2), fill=bg)
        draw.text((lx + 1, 3), label, fill=fg, font=font)

    for y in range(step, h, step):
        draw.line((0, y, tick_len, y), fill=fg, width=1)
        draw.line((max(0, w - tick_len - 1), y, w - 1, y), fill=fg, width=1)
        label = str(y)
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        ly = min(max(0, y + 2), max(0, h - th - 2))
        draw.rectangle((2, ly, 2 + tw + 2, ly + th + 2), fill=bg)
        draw.text((3, ly + 1), label, fill=fg, font=font)

    return out


def draw_marks(img: Image.Image, marks_in_image: list[tuple[int, Rect]]) -> Image.Image:
    """Return a copy of *img* with numbered Set-of-Mark bounding boxes."""
    out = _ensure_rgb_copy(img)
    w, h = out.size
    draw = ImageDraw.Draw(out)
    font = ImageFont.load_default()

    for idx, (mark_id, rect) in enumerate(marks_in_image):
        color = _MARK_PALETTE[idx % len(_MARK_PALETTE)]
        left = max(0, min(w - 1, rect.left))
        top = max(0, min(h - 1, rect.top))
        right = max(left, min(w - 1, rect.right - 1))
        bottom = max(top, min(h - 1, rect.bottom - 1))

        draw.rectangle((left, top, right, bottom), outline=color, width=2)

        label = str(mark_id)
        tb = draw.textbbox((0, 0), label, font=font)
        tw = tb[2] - tb[0]
        th = tb[3] - tb[1]
        bx = min(left, max(0, w - tw - 6))
        by = max(0, top - th - 4) if top >= th + 4 else top
        draw.rectangle((bx, by, bx + tw + 4, by + th + 4), fill=color)
        draw.text((bx + 2, by + 2), label, fill=(0, 0, 0), font=font)

    return out


def zoom_crop(
    original: Image.Image,
    crop: Rect,
    max_edge: int,
    factor: float | None = None,
) -> Image.Image:
    """Crop *crop* from *original* and scale up to 4x while respecting *max_edge*."""
    if max_edge <= 0:
        raise EdmError(
            ErrorCode.INVALID_ARGUMENT,
            f"max_edge must be positive, got {max_edge}.",
            details={"max_edge": max_edge},
        )
    if crop.width <= 0 or crop.height <= 0:
        raise EdmError(
            ErrorCode.INVALID_ARGUMENT,
            f"Zoom crop must have positive dimensions, got {crop}.",
            details={"crop": crop.as_list()},
        )

    ow, oh = original.size
    left = max(0, min(ow, crop.left))
    top = max(0, min(oh, crop.top))
    right = max(0, min(ow, crop.right))
    bottom = max(0, min(oh, crop.bottom))
    if right <= left or bottom <= top:
        raise EdmError(
            ErrorCode.POINT_OUT_OF_BOUNDS,
            f"Zoom crop {crop.as_list()} lies outside image bounds {ow}x{oh}.",
            details={"crop": crop.as_list(), "image_size": [ow, oh]},
        )

    cropped = original.crop((left, top, right, bottom))
    cw, ch = cropped.size
    longest = max(cw, ch)
    max_scale_by_edge = max_edge / longest

    if factor is None:
        scale = min(_MAX_ZOOM_FACTOR, max_scale_by_edge)
    else:
        if not math.isfinite(factor) or factor <= 0:
            raise EdmError(
                ErrorCode.INVALID_ARGUMENT,
                f"Zoom factor must be positive and finite, got {factor}.",
                details={"factor": factor},
            )
        scale = min(min(factor, _MAX_ZOOM_FACTOR), max_scale_by_edge)

    target_w = max(1, min(max_edge, round(cw * scale)))
    target_h = max(1, min(max_edge, round(ch * scale)))
    if (target_w, target_h) == (cw, ch):
        return cropped
    return cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)


def encode_image(img: Image.Image, max_bytes: int) -> tuple[bytes, str]:
    """Encode *img* as lossless PNG, falling back to JPEG 85->75->60 to fit *max_bytes*."""
    if max_bytes <= 0:
        raise EdmError(
            ErrorCode.INVALID_ARGUMENT,
            f"max_bytes must be positive, got {max_bytes}.",
            details={"max_bytes": max_bytes},
        )

    png_buf = BytesIO()
    img.save(png_buf, format="PNG")
    png_data = png_buf.getvalue()
    if len(png_data) <= max_bytes:
        return (png_data, "image/png")

    rgb = img if img.mode == "RGB" else img.convert("RGB")
    last_data = b""
    for quality in _JPEG_QUALITIES:
        jpg_buf = BytesIO()
        rgb.save(jpg_buf, format="JPEG", quality=quality, optimize=True)
        last_data = jpg_buf.getvalue()
        if len(last_data) <= max_bytes:
            return (last_data, "image/jpeg")

    return (last_data, "image/jpeg")
