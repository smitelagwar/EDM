import pytest

from edm import __version__
from edm.cli import main


def test_version_string() -> None:
    assert __version__ == "0.1.0rc1"


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["--version"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "0.1.0rc1" in captured.out
