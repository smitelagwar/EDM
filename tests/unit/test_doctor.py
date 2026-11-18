import json
from pathlib import Path

import pytest

from edm.cli import main
from edm.config import Config
from edm.fakes import FakeCaptureBackend, FakeInputSink, FakeSession
from edm.service import Edm


def test_doctor_keys(fake_edm: Edm) -> None:
    res = fake_edm.doctor()
    payload = res.payload
    expected_keys = {
        "version",
        "python",
        "os_build",
        "session",
        "elevated",
        "integrity",
        "dpi_awareness",
        "monitors",
        "virtual_screen",
        "backends",
        "killswitch",
        "data_dir",
        "hints",
    }
    assert expected_keys.issubset(payload.keys())
    assert payload["session"]["state"] == "ok"
    assert isinstance(payload["monitors"], list)
    assert len(payload["monitors"]) >= 1
    assert "ocr" in payload["backends"]
    assert "available" in payload["backends"]["ocr"]
    assert "languages" in payload["backends"]["ocr"]
    assert payload["hints"] == []


def test_doctor_isolated_hint(tmp_path: Path) -> None:
    cfg = Config(data_dir=tmp_path / "edm-data")
    edm = Edm(
        cfg,
        session_provider=FakeSession(state="isolated_desktop"),
        capture_backends={"fake": FakeCaptureBackend()},
        input_sink=FakeInputSink(),
    )
    res = edm.doctor()
    assert res.payload["session"]["state"] == "isolated_desktop"
    assert len(res.payload["hints"]) >= 1
    assert "MCP" in res.payload["hints"][0]


def test_cli_doctor_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("EDM_FAKE", "1")
    rc = main(["doctor"])
    captured = capsys.readouterr()
    assert rc == 0
    data = json.loads(captured.out)
    assert data["version"] == "0.1.0.dev0"
    assert data["session"]["state"] == "ok"
