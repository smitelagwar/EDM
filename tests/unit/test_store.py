"""Unit tests for edm.observe.store."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from PIL import Image

from edm.config import Config
from edm.errors import EdmError, ErrorCode
from edm.geometry import ImageMapping, Rect
from edm.observe.store import Mark, ObservationStore


@dataclass
class _FakeFrame:
    image: Image.Image
    screen_rect: Rect
    backend: str
    captured_at: float


def _make_frame(
    w: int = 200, h: int = 100, color: tuple[int, int, int] = (40, 80, 120)
) -> _FakeFrame:
    return _FakeFrame(
        image=Image.new("RGB", (w, h), color),
        screen_rect=Rect(0, 0, w, h),
        backend="fake",
        captured_at=1_700_000_000.0,
    )


def test_store_roundtrip_new_instance(tmp_path: Path) -> None:
    cfg = Config(data_dir=tmp_path)
    now = 1_700_000_000.0
    store1 = ObservationStore(tmp_path, cfg, clock=lambda: now)

    frame = _make_frame(2560, 1440)
    preview = Image.new("RGB", (1600, 900), (10, 20, 30))
    mapping = ImageMapping(
        frame_rect=Rect(0, 0, 2560, 1440),
        crop=Rect(0, 0, 2560, 1440),
        image_size=(1600, 900),
    )
    marks = [Mark(id=1, rect=Rect(10, 20, 110, 60), label="OK")]

    obs = store1.add(
        frame,
        preview,
        mapping,
        target="screen",
        window={"hwnd": 42, "title": "Test"},
        parent_id=None,
        marks=marks,
        tags=("shot", "main"),
    )

    assert obs.original_path.is_file()
    assert obs.preview_path.is_file()

    public = obs.to_public()
    assert public["id"] == obs.id
    assert public["target"] == "screen"
    assert public["image_size"] == [1600, 900]
    assert public["frame_rect"] == [0, 0, 2560, 1440]
    assert public["scale"] == pytest.approx(0.625)
    assert public["backend"] == "fake"
    assert public["parent_id"] is None

    store2 = ObservationStore(tmp_path, cfg, clock=lambda: now)
    loaded = store2.get(obs.id)
    assert loaded.id == obs.id
    assert loaded.mapping == mapping
    assert loaded.frame_rect == frame.screen_rect
    assert loaded.marks == marks
    assert loaded.tags == ["shot", "main"]
    assert loaded.window == {"hwnd": 42, "title": "Test"}

    orig = store2.load_original(loaded)
    assert orig.size == (2560, 1440)


def test_store_get_missing_raises(tmp_path: Path) -> None:
    store = ObservationStore(tmp_path, Config(data_dir=tmp_path))
    with pytest.raises(EdmError) as exc_info:
        store.get("o-20260101-000000-9999")
    assert exc_info.value.code == ErrorCode.OBSERVATION_NOT_FOUND


def test_store_latest_and_tags(tmp_path: Path) -> None:
    t = 1_700_000_000.0
    store = ObservationStore(tmp_path, Config(data_dir=tmp_path), clock=lambda: t)
    assert store.latest() is None

    frame = _make_frame(100, 100)
    mapping = ImageMapping(Rect(0, 0, 100, 100), Rect(0, 0, 100, 100), (100, 100))
    obs1 = store.add(frame, frame.image, mapping, target="screen", tags=["alpha"])
    t += 1.0
    obs2 = store.add(frame, frame.image, mapping, target="screen", tags=["beta"])

    assert store.latest() is not None
    assert store.latest().id == obs2.id
    assert store.latest(tag="alpha") is not None
    assert store.latest(tag="alpha").id == obs1.id
    assert store.latest(tag="gamma") is None


def test_store_id_unique_1000(tmp_path: Path) -> None:
    fixed_time = 1_700_000_000.0
    store = ObservationStore(tmp_path, Config(data_dir=tmp_path), clock=lambda: fixed_time)
    frame = _make_frame(16, 16)
    mapping = ImageMapping(Rect(0, 0, 16, 16), Rect(0, 0, 16, 16), (16, 16))

    ids: set[str] = set()
    for _ in range(1000):
        obs = store.add(frame, frame.image, mapping, target="screen")
        assert obs.id.startswith("o-")
        ids.add(obs.id)

    assert len(ids) == 1000


def test_prune_by_age(tmp_path: Path) -> None:
    now = 1_700_000_000.0
    cfg = Config(data_dir=tmp_path, retention_days=7)
    store = ObservationStore(tmp_path, cfg, clock=lambda: now)

    frame = _make_frame(64, 64)
    mapping = ImageMapping(Rect(0, 0, 64, 64), Rect(0, 0, 64, 64), (64, 64))

    old_obs = store.add(frame, frame.image, mapping, target="screen")

    now += 8 * 86400.0
    fresh_obs = store.add(frame, frame.image, mapping, target="screen")

    pruned = store.prune(now=now)
    assert pruned == 1
    assert not old_obs.original_path.exists()
    assert not old_obs.preview_path.exists()
    assert fresh_obs.original_path.exists()

    with pytest.raises(EdmError) as exc_info:
        store.get(old_obs.id)
    assert exc_info.value.code == ErrorCode.OBSERVATION_NOT_FOUND
    assert store.get(fresh_obs.id).id == fresh_obs.id


def test_prune_by_bytes(tmp_path: Path) -> None:
    now = 1_700_000_000.0
    # Use a small retention_bytes limit so adding 3 noisy images exceeds it
    cfg = Config(data_dir=tmp_path, retention_days=7, retention_bytes=15_000)
    store = ObservationStore(tmp_path, cfg, clock=lambda: now)

    import os

    rng_bytes = os.urandom(120 * 120 * 3)
    noisy = Image.frombytes("RGB", (120, 120), rng_bytes)
    frame = _FakeFrame(
        image=noisy, screen_rect=Rect(0, 0, 120, 120), backend="fake", captured_at=now
    )
    mapping = ImageMapping(Rect(0, 0, 120, 120), Rect(0, 0, 120, 120), (120, 120))

    obs_list = []
    for i in range(3):
        now += i + 1
        obs_list.append(store.add(frame, noisy, mapping, target="screen"))

    pruned = store.prune(now=now)
    assert pruned >= 2
    assert not obs_list[0].original_path.exists()
    # At least the newest or remaining fits within retention_bytes
    remaining_bytes = sum(
        p.stat().st_size for o in obs_list for p in (o.original_path, o.preview_path) if p.exists()
    )
    assert remaining_bytes <= cfg.retention_bytes


def test_corrupt_index_line_skipped(tmp_path: Path) -> None:
    now = 1_700_000_000.0
    cfg = Config(data_dir=tmp_path)
    store = ObservationStore(tmp_path, cfg, clock=lambda: now)

    frame = _make_frame(32, 32)
    mapping = ImageMapping(Rect(0, 0, 32, 32), Rect(0, 0, 32, 32), (32, 32))
    obs = store.add(frame, frame.image, mapping, target="screen")

    index_path = tmp_path / "index.jsonl"
    with index_path.open("a", encoding="utf-8") as fh:
        fh.write("{corrupt json line\n")
        fh.write("not-even-json\n")

    store2 = ObservationStore(tmp_path, cfg, clock=lambda: now)
    assert store2.get(obs.id).id == obs.id
    assert store2.latest() is not None
    assert store2.latest().id == obs.id
