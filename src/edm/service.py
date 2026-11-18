"""Core EDM service facade."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from edm.config import Config, load_config
from edm.doctor import run_doctor
from edm.fakes import FakeCaptureBackend, FakeInputSink, FakeSession
from edm.win32.dpi import ensure_dpi_awareness
from edm.win32.session import SessionInfo, get_session


@dataclass(frozen=True)
class Result:
    """Unified return envelope for EDM service operations."""

    payload: dict[str, Any]
    image: bytes | None = None
    mime: str | None = None


class Edm:
    """Facade coordinating session, capture, perception, and input backends."""

    def __init__(
        self,
        cfg: Config | None = None,
        *,
        session_provider: Callable[[], SessionInfo] = get_session,
        capture_backends: dict[str, Any] | None = None,
        input_sink: Any = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.dpi_awareness = ensure_dpi_awareness()
        self.cfg = cfg if cfg is not None else load_config()
        self.session_provider = session_provider
        self.capture_backends = dict(capture_backends) if capture_backends is not None else {}
        self.input_sink = input_sink
        self.clock = clock

    @classmethod
    def build_default(cls, cfg: Config | None = None) -> Edm:
        """Build an ``Edm`` instance, using fake backends when ``EDM_FAKE=1``."""
        if os.environ.get("EDM_FAKE") == "1":
            return cls(
                cfg,
                session_provider=FakeSession(),
                capture_backends={"fake": FakeCaptureBackend()},
                input_sink=FakeInputSink(),
            )
        return cls(cfg)

    def doctor(self) -> Result:
        """Run environment diagnostics and return a ``Result``."""
        return Result(payload=run_doctor(self))
