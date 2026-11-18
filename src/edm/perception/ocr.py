"""Offline Windows OCR engine wrapper and Turkish-aware text matching."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable, Coroutine, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Literal

from PIL import Image

from edm.errors import EdmError, ErrorCode
from edm.geometry import Rect
from edm.perception.textnorm import tr_fold

MatchMode = Literal["contains", "exact", "regex"]

_UPSCALE_MIN_EDGE = 800


@dataclass(frozen=True)
class OcrWord:
    """Single recognized word with its bounding box in input image coordinates."""

    text: str
    rect: Rect


@dataclass(frozen=True)
class OcrLine:
    """Single recognized line of text and its constituent words."""

    text: str
    words: list[OcrWord]
    rect: Rect


@dataclass(frozen=True)
class TextMatch:
    """Matched text span and its bounding box in input image coordinates."""

    text: str
    rect_image: Rect


def _union_rects(rects: Sequence[Rect]) -> Rect:
    return Rect(
        left=min(r.left for r in rects),
        top=min(r.top for r in rects),
        right=max(r.right for r in rects),
        bottom=max(r.bottom for r in rects),
    )


def _run_async[T](coro_factory: Callable[[], Coroutine[Any, Any, T]]) -> T:
    """Run an async coroutine safely whether or not an event loop is already running."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro_factory())
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro_factory()).result()


def available_ocr_languages() -> list[str]:
    """Return installed Windows OCR language tags, or [] on error."""
    try:
        from winrt.windows.media.ocr import OcrEngine

        return [str(lang.language_tag) for lang in OcrEngine.available_recognizer_languages]
    except Exception:
        return []


def _create_default_engine(lang: str | None) -> Any:
    """Instantiate a WinRT OcrEngine for `lang`, Turkish ('tr*'), or user profile."""
    try:
        from winrt.windows.globalization import Language
        from winrt.windows.media.ocr import OcrEngine
    except Exception as exc:
        raise EdmError(
            ErrorCode.DEPENDENCY_MISSING,
            f"Windows OCR runtime dependencies are missing: {exc}",
        ) from exc

    if lang is not None:
        try:
            engine = OcrEngine.try_create_from_language(Language(lang))
        except Exception as exc:
            raise EdmError(
                ErrorCode.DEPENDENCY_MISSING,
                f"Windows OCR language pack missing for '{lang}'. "
                "Install it in Windows Settings -> Time & language -> Language & region.",
            ) from exc
        if engine is None:
            raise EdmError(
                ErrorCode.DEPENDENCY_MISSING,
                f"Windows OCR language pack missing for '{lang}'. "
                "Install it in Windows Settings -> Time & language -> Language & region.",
            )
        return engine

    langs = list(OcrEngine.available_recognizer_languages)
    tr_lang = next((item for item in langs if item.language_tag.lower() == "tr-tr"), None)
    if tr_lang is None:
        tr_lang = next(
            (item for item in langs if item.language_tag.lower().startswith("tr")),
            None,
        )

    engine = OcrEngine.try_create_from_language(tr_lang) if tr_lang is not None else None
    if engine is None:
        engine = OcrEngine.try_create_from_user_profile_languages()

    if engine is None:
        raise EdmError(
            ErrorCode.DEPENDENCY_MISSING,
            "Windows OCR language pack missing. Install a language pack (e.g. Turkish 'tr-TR' "
            "or English) in Windows Settings -> Time & language -> Language & region.",
        )
    return engine


def _to_software_bitmap(img: Image.Image) -> Any:
    """Convert a PIL Image into a WinRT SoftwareBitmap (RGBA8 premultiplied)."""
    from winrt.windows.graphics.imaging import (
        BitmapAlphaMode,
        BitmapPixelFormat,
        SoftwareBitmap,
    )
    from winrt.windows.storage.streams import DataWriter

    rgba = img.convert("RGBA")
    writer = DataWriter()
    writer.write_bytes(rgba.tobytes())
    buf = writer.detach_buffer()
    return SoftwareBitmap.create_copy_from_buffer(
        buf,
        BitmapPixelFormat.RGBA8,
        rgba.width,
        rgba.height,
        BitmapAlphaMode.PREMULTIPLIED,
    )


def ocr_image(
    img: Image.Image,
    lang: str | None = None,
    *,
    engine: Any = None,
) -> list[OcrLine]:
    """Run offline Windows OCR on `img` and return recognized lines in input coordinates."""
    w, h = img.size
    if w <= 0 or h <= 0:
        raise EdmError(
            ErrorCode.INVALID_ARGUMENT,
            f"ocr_image requires positive image dimensions, got {img.size}.",
        )

    upscaled = min(w, h) < _UPSCALE_MIN_EDGE
    work_img = img.resize((w * 2, h * 2), Image.Resampling.BICUBIC) if upscaled else img
    inv_scale = 0.5 if upscaled else 1.0

    active_engine = engine if engine is not None else _create_default_engine(lang)
    bitmap = _to_software_bitmap(work_img)

    async def _recognize() -> Any:
        return await active_engine.recognize_async(bitmap)

    result = _run_async(_recognize)

    lines: list[OcrLine] = []
    for raw_line in result.lines:
        words: list[OcrWord] = []
        for raw_word in raw_line.words:
            br = raw_word.bounding_rect
            left = round(float(br.x) * inv_scale)
            top = round(float(br.y) * inv_scale)
            right = round((float(br.x) + float(br.width)) * inv_scale)
            bottom = round((float(br.y) + float(br.height)) * inv_scale)
            words.append(OcrWord(text=str(raw_word.text), rect=Rect(left, top, right, bottom)))
        if not words:
            continue
        lines.append(
            OcrLine(
                text=str(raw_line.text),
                words=words,
                rect=_union_rects([word.rect for word in words]),
            )
        )
    return lines


def _regex_match_rect(line: OcrLine, start: int, end: int) -> Rect:
    """Map a character span in `line.text` to the union rect of overlapping words."""
    if not line.words:
        return line.rect
    overlapping: list[Rect] = []
    cursor = 0
    for word in line.words:
        idx = line.text.find(word.text, cursor)
        if idx == -1:
            continue
        w_start = idx
        w_end = idx + len(word.text)
        cursor = w_end
        if w_start < end and w_end > start:
            overlapping.append(word.rect)
    return _union_rects(overlapping) if overlapping else line.rect


def match_text(
    lines: list[OcrLine],
    query: str,
    match: MatchMode = "contains",
) -> list[TextMatch]:
    """Find text matches across OCR lines using Turkish folding or regex."""
    if not query:
        raise EdmError(ErrorCode.INVALID_ARGUMENT, "OCR search query must not be empty.")

    if match == "regex":
        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error as exc:
            raise EdmError(ErrorCode.INVALID_ARGUMENT, f"Invalid regex query: {exc}") from exc
        matches: list[TextMatch] = []
        for line in lines:
            found = pattern.search(line.text)
            if found is not None:
                rect = _regex_match_rect(line, found.start(), found.end())
                matches.append(TextMatch(text=found.group(0), rect_image=rect))
        return matches

    if match not in ("contains", "exact"):
        raise EdmError(ErrorCode.INVALID_ARGUMENT, f"Unsupported match mode: {match!r}")

    q_folded = tr_fold(query).strip()
    if not q_folded:
        raise EdmError(ErrorCode.INVALID_ARGUMENT, "OCR search query must not be whitespace.")
    q_tokens = q_folded.split()

    results: list[TextMatch] = []
    for line in lines:
        if len(q_tokens) == 1:
            token = q_tokens[0]
            if line.words:
                for word in line.words:
                    w_fold = tr_fold(word.text)
                    hit = w_fold == token if match == "exact" else token in w_fold
                    if hit:
                        results.append(TextMatch(text=word.text, rect_image=word.rect))
            else:
                l_fold = tr_fold(line.text)
                hit = l_fold == token if match == "exact" else token in l_fold
                if hit:
                    results.append(TextMatch(text=line.text, rect_image=line.rect))
            continue

        k = len(q_tokens)
        if len(line.words) < k:
            continue
        for idx in range(len(line.words) - k + 1):
            window = line.words[idx : idx + k]
            w_tokens = [tr_fold(w.text) for w in window]
            if match == "exact":
                hit = w_tokens == q_tokens
            else:
                hit = (
                    q_tokens[0] in w_tokens[0]
                    and q_tokens[-1] in w_tokens[-1]
                    and w_tokens[1:-1] == q_tokens[1:-1]
                )
            if hit:
                results.append(
                    TextMatch(
                        text=" ".join(w.text for w in window),
                        rect_image=_union_rects([w.rect for w in window]),
                    )
                )
    return results
