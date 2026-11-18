"""Unit tests for offline Windows OCR matching, Turkish folding, and scaling."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image

from edm.errors import EdmError, ErrorCode
from edm.geometry import Rect
from edm.perception.ocr import OcrLine, OcrWord, match_text, ocr_image
from edm.perception.textnorm import tr_fold


def test_tr_fold() -> None:
    """Turkish I/İ folding converts uppercase dotted/dotless I accurately."""
    assert tr_fold("ŞÜPHE İĞNE IŞIK") == "şüphe iğne ışık"


def test_match_contains_turkish() -> None:
    """Contains matching folds Turkish characters without confusing I and İ."""
    lines = [
        OcrLine(
            text="İŞLEM IŞIK ŞÜPHE",
            words=[
                OcrWord("İŞLEM", Rect(10, 10, 60, 30)),
                OcrWord("IŞIK", Rect(70, 10, 110, 30)),
                OcrWord("ŞÜPHE", Rect(120, 10, 180, 30)),
            ],
            rect=Rect(10, 10, 180, 30),
        )
    ]

    m_islem = match_text(lines, "işlem", match="contains")
    assert len(m_islem) == 1
    assert m_islem[0].text == "İŞLEM"
    assert m_islem[0].rect_image == Rect(10, 10, 60, 30)

    # Turkish dotless I ('IŞIK' -> 'ışık') must NOT match dotted 'işik'.
    assert match_text(lines, "işik", match="contains") == []
    m_isik = match_text(lines, "ışık", match="contains")
    assert len(m_isik) == 1
    assert m_isik[0].rect_image == Rect(70, 10, 110, 30)


def test_match_multiword_union_rect() -> None:
    """Multi-word query returns the union rectangle of consecutive matching words."""
    lines = [
        OcrLine(
            text="Çalışma Ağı İğne Şüphe",
            words=[
                OcrWord("Çalışma", Rect(10, 20, 80, 40)),
                OcrWord("Ağı", Rect(90, 22, 130, 42)),
                OcrWord("İğne", Rect(140, 18, 185, 39)),
                OcrWord("Şüphe", Rect(195, 20, 250, 40)),
            ],
            rect=Rect(10, 18, 250, 42),
        )
    ]

    matches = match_text(lines, "ağI iĞnE", match="contains")
    assert len(matches) == 1
    assert matches[0].text == "Ağı İğne"
    assert matches[0].rect_image == Rect(90, 18, 185, 42)

    exact_matches = match_text(lines, "AĞI İĞNE", match="exact")
    assert len(exact_matches) == 1
    assert exact_matches[0].rect_image == Rect(90, 18, 185, 42)


def test_match_regex() -> None:
    """Regex matching is case-insensitive and raises INVALID_ARGUMENT on bad patterns."""
    lines = [
        OcrLine(
            text="Sipariş No: 4821",
            words=[
                OcrWord("Sipariş", Rect(10, 10, 70, 30)),
                OcrWord("No:", Rect(75, 10, 105, 30)),
                OcrWord("4821", Rect(110, 10, 155, 30)),
            ],
            rect=Rect(10, 10, 155, 30),
        )
    ]

    matches = match_text(lines, r"no:\s+\d{4}", match="regex")
    assert len(matches) == 1
    assert matches[0].text == "No: 4821"
    assert matches[0].rect_image == Rect(75, 10, 155, 30)

    with pytest.raises(EdmError) as exc_info:
        match_text(lines, "[unclosed", match="regex")
    assert exc_info.value.code == ErrorCode.INVALID_ARGUMENT


def test_ocr_upscale_maps_back() -> None:
    """Images with short edge < 800 are upscaled 2x and OCR rects are scaled back by 0.5."""

    class FakeOcrEngine:
        def __init__(self) -> None:
            self.seen_size: tuple[int, int] | None = None

        async def recognize_async(self, bitmap: Any) -> object:
            w = int(bitmap.pixel_width)
            h = int(bitmap.pixel_height)
            self.seen_size = (w, h)
            word = SimpleNamespace(
                text="Test",
                bounding_rect=SimpleNamespace(x=100.0, y=100.0, width=100.0, height=40.0),
            )
            line = SimpleNamespace(text="Test", words=[word])
            return SimpleNamespace(lines=[line])

    img = Image.new("RGB", (400, 300), (255, 255, 255))
    engine = FakeOcrEngine()
    lines = ocr_image(img, engine=engine)

    assert engine.seen_size == (800, 600)
    assert len(lines) == 1
    assert lines[0].words[0].rect == Rect(50, 50, 100, 70)
    assert lines[0].rect == Rect(50, 50, 100, 70)


def test_ocr_inside_running_event_loop() -> None:
    """ocr_image works safely when called from inside an active asyncio event loop."""

    class FakeOcrEngine:
        async def recognize_async(self, bitmap: object) -> object:
            del bitmap
            word = SimpleNamespace(
                text="Merhaba",
                bounding_rect=SimpleNamespace(x=10.0, y=20.0, width=80.0, height=30.0),
            )
            return SimpleNamespace(lines=[SimpleNamespace(text="Merhaba", words=[word])])

    img = Image.new("RGB", (1000, 900), (255, 255, 255))

    async def _run() -> list[OcrLine]:
        return ocr_image(img, engine=FakeOcrEngine())

    lines = asyncio.run(_run())
    assert len(lines) == 1
    assert lines[0].text == "Merhaba"
    assert lines[0].rect == Rect(10, 20, 90, 50)
