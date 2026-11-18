"""Disk-backed observation store with JSONL indexing and retention pruning."""

from __future__ import annotations

import json
import secrets
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from PIL import Image

from edm.config import Config
from edm.errors import EdmError, ErrorCode
from edm.geometry import ImageMapping, Rect
from edm.observe.render import encode_image

_PRUNE_INTERVAL = 50
_SECONDS_PER_DAY = 86400.0


class FrameLike(Protocol):
    """Structural protocol matching ``edm.capture.base.Frame``."""

    @property
    def image(self) -> Image.Image: ...
    @property
    def screen_rect(self) -> Rect: ...
    @property
    def backend(self) -> str: ...
    @property
    def captured_at(self) -> float: ...


@dataclass(frozen=True)
class Mark:
    """Labeled UI element bounding box in screen coordinates."""

    id: int
    rect: Rect
    label: str


@dataclass(frozen=True)
class Observation:
    """Persisted capture or zoom observation with coordinate mapping."""

    id: str
    created_at: float
    target: str
    frame_rect: Rect
    mapping: ImageMapping
    original_path: Path
    preview_path: Path
    backend: str
    window: dict[str, Any] | None
    parent_id: str | None
    marks: list[Mark]
    tags: list[str]

    def to_public(self) -> dict[str, Any]:
        """Serialize into the public §10.1 observation envelope."""
        return {
            "id": self.id,
            "target": self.target,
            "image_size": [self.mapping.image_size[0], self.mapping.image_size[1]],
            "frame_rect": self.frame_rect.as_list(),
            "scale": self.mapping.scale,
            "backend": self.backend,
            "path": self.original_path.as_posix(),
            "parent_id": self.parent_id,
        }


def _rect_from_list(raw: Any) -> Rect:
    if not isinstance(raw, list) or len(raw) != 4:
        raise ValueError("Rect must be a 4-element list.")
    return Rect(int(raw[0]), int(raw[1]), int(raw[2]), int(raw[3]))


def _obs_to_dict(obs: Observation) -> dict[str, Any]:
    return {
        "id": obs.id,
        "created_at": obs.created_at,
        "target": obs.target,
        "frame_rect": obs.frame_rect.as_list(),
        "mapping": {
            "frame_rect": obs.mapping.frame_rect.as_list(),
            "crop": obs.mapping.crop.as_list(),
            "image_size": [obs.mapping.image_size[0], obs.mapping.image_size[1]],
        },
        "original_path": str(obs.original_path),
        "preview_path": str(obs.preview_path),
        "backend": obs.backend,
        "window": obs.window,
        "parent_id": obs.parent_id,
        "marks": [{"id": m.id, "rect": m.rect.as_list(), "label": m.label} for m in obs.marks],
        "tags": obs.tags,
    }


def _obs_from_dict(data: dict[str, Any]) -> Observation:
    map_raw = data["mapping"]
    img_size_raw = map_raw["image_size"]
    if not isinstance(img_size_raw, list) or len(img_size_raw) != 2:
        raise ValueError("image_size must be a 2-element list.")
    mapping = ImageMapping(
        frame_rect=_rect_from_list(map_raw["frame_rect"]),
        crop=_rect_from_list(map_raw["crop"]),
        image_size=(int(img_size_raw[0]), int(img_size_raw[1])),
    )
    marks_raw = data.get("marks") or []
    marks = [
        Mark(id=int(m["id"]), rect=_rect_from_list(m["rect"]), label=str(m["label"]))
        for m in marks_raw
    ]
    tags_raw = data.get("tags") or []
    window_raw = data.get("window")
    window = dict(window_raw) if isinstance(window_raw, dict) else None
    parent_raw = data.get("parent_id")
    parent_id = str(parent_raw) if parent_raw is not None else None

    return Observation(
        id=str(data["id"]),
        created_at=float(data["created_at"]),
        target=str(data["target"]),
        frame_rect=_rect_from_list(data["frame_rect"]),
        mapping=mapping,
        original_path=Path(str(data["original_path"])),
        preview_path=Path(str(data["preview_path"])),
        backend=str(data["backend"]),
        window=window,
        parent_id=parent_id,
        marks=marks,
        tags=[str(t) for t in tags_raw],
    )


def _obs_disk_bytes(obs: Observation) -> int:
    total = 0
    for path in (obs.original_path, obs.preview_path):
        try:
            if path.is_file():
                total += path.stat().st_size
        except OSError:
            pass
    return total


class ObservationStore:
    """Disk-backed store for observations under ``root``."""

    def __init__(
        self,
        root: Path,
        cfg: Config,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.root = root
        self.cfg = cfg
        self._clock = clock
        self._index_path = self.root / "index.jsonl"
        self._obs_dir = self.root / "observations"
        self._add_count = 0
        self._seen_ids: set[str] = set()

    def _next_id(self, created_at: float, day_dir: Path) -> str:
        stamp = datetime.fromtimestamp(created_at).strftime("%Y%m%d-%H%M%S")
        for _ in range(10000):
            suffix = secrets.randbelow(10000)
            candidate = f"o-{stamp}-{suffix:04d}"
            if candidate in self._seen_ids:
                continue
            if (day_dir / f"{candidate}.png").exists():
                self._seen_ids.add(candidate)
                continue
            self._seen_ids.add(candidate)
            return candidate
        raise EdmError(
            ErrorCode.INTERNAL,
            "Exhausted unique observation ID candidates within the same second.",
        )

    def _read_all(self) -> list[Observation]:
        if not self._index_path.is_file():
            return []
        observations: list[Observation] = []
        with self._index_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    raw = json.loads(stripped)
                    if not isinstance(raw, dict):
                        continue
                    observations.append(_obs_from_dict(raw))
                except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                    continue
        return observations

    def add(
        self,
        frame: FrameLike,
        preview: Image.Image,
        mapping: ImageMapping,
        *,
        target: str,
        window: dict[str, Any] | None = None,
        parent_id: str | None = None,
        marks: list[Mark] | None = None,
        tags: Sequence[str] = (),
    ) -> Observation:
        """Persist *frame* original PNG, encoded *preview*, and index metadata."""
        created_at = self._clock()
        dt = datetime.fromtimestamp(created_at)
        day_dir = self._obs_dir / dt.strftime("%Y-%m-%d")
        day_dir.mkdir(parents=True, exist_ok=True)

        obs_id = self._next_id(created_at, day_dir)
        original_path = day_dir / f"{obs_id}.png"
        frame.image.save(original_path, format="PNG")

        preview_bytes, mime = encode_image(preview, self.cfg.max_image_bytes)
        preview_ext = ".png" if mime == "image/png" else ".jpg"
        preview_path = day_dir / f"{obs_id}.preview{preview_ext}"
        preview_path.write_bytes(preview_bytes)

        obs = Observation(
            id=obs_id,
            created_at=created_at,
            target=target,
            frame_rect=frame.screen_rect,
            mapping=mapping,
            original_path=original_path,
            preview_path=preview_path,
            backend=frame.backend,
            window=dict(window) if window is not None else None,
            parent_id=parent_id,
            marks=list(marks) if marks is not None else [],
            tags=list(tags),
        )

        self.root.mkdir(parents=True, exist_ok=True)
        with self._index_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(_obs_to_dict(obs), ensure_ascii=False) + "\n")

        self._add_count += 1
        if self._add_count % _PRUNE_INTERVAL == 0:
            self.prune(now=created_at)

        return obs

    def get(self, obs_id: str) -> Observation:
        """Return the observation with *obs_id* or raise ``OBSERVATION_NOT_FOUND``."""
        for obs in reversed(self._read_all()):
            if obs.id == obs_id:
                return obs
        raise EdmError(
            ErrorCode.OBSERVATION_NOT_FOUND,
            f"Observation '{obs_id}' not found.",
            details={"observation_id": obs_id},
        )

    def latest(self, tag: str | None = None) -> Observation | None:
        """Return the most recent observation, optionally filtered by *tag*."""
        for obs in reversed(self._read_all()):
            if tag is None or tag in obs.tags:
                return obs
        return None

    def list_by_tag(self, tag: str, limit: int = 1) -> list[Observation]:
        """Return up to *limit* most recent observations carrying *tag*, newest first."""
        if limit <= 0:
            return []
        matched = [obs for obs in reversed(self._read_all()) if tag in obs.tags]
        return matched[:limit]

    def load_original(self, obs: Observation) -> Image.Image:
        """Load the full-resolution original PNG for *obs*."""
        if not obs.original_path.is_file():
            raise EdmError(
                ErrorCode.OBSERVATION_NOT_FOUND,
                f"Original image missing for observation '{obs.id}'.",
                details={"observation_id": obs.id, "path": str(obs.original_path)},
            )
        with Image.open(obs.original_path) as im:
            return im.copy() if im.mode == "RGB" else im.convert("RGB")

    def prune(self, now: float | None = None) -> int:
        """Remove observations exceeding retention age or total byte budget."""
        now_ts = self._clock() if now is None else now
        cutoff = now_ts - self.cfg.retention_days * _SECONDS_PER_DAY
        records = self._read_all()
        if not records:
            return 0

        to_delete: list[Observation] = []
        remaining: list[Observation] = []
        for obs in records:
            if obs.created_at < cutoff:
                to_delete.append(obs)
            else:
                remaining.append(obs)

        remaining.sort(key=lambda o: o.created_at)
        total_bytes = sum(_obs_disk_bytes(o) for o in remaining)
        while remaining and total_bytes > self.cfg.retention_bytes:
            oldest = remaining.pop(0)
            total_bytes -= _obs_disk_bytes(oldest)
            to_delete.append(oldest)

        for obs in to_delete:
            for path in (obs.original_path, obs.preview_path):
                path.unlink(missing_ok=True)
            self._seen_ids.discard(obs.id)

        if self._obs_dir.is_dir():
            for child in self._obs_dir.iterdir():
                if child.is_dir() and not any(child.iterdir()):
                    child.rmdir()

        self.root.mkdir(parents=True, exist_ok=True)
        with self._index_path.open("w", encoding="utf-8") as fh:
            for obs in remaining:
                fh.write(json.dumps(_obs_to_dict(obs), ensure_ascii=False) + "\n")

        return len(to_delete)
