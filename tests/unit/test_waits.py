import pytest

from edm.actions.waits import wait_until
from edm.errors import EdmError, ErrorCode
from edm.service import Edm


def test_wait_until_timeout_fast() -> None:
    assert wait_until(lambda: False, timeout_s=0.15, interval_s=0.05) is False


def test_wait_for_rejects_over_60(fake_edm: Edm) -> None:
    with pytest.raises(EdmError) as exc_info:
        fake_edm.wait_for("stable", timeout_s=61.0)
    assert exc_info.value.code == ErrorCode.INVALID_ARGUMENT


def test_wait_for_kinds_fake(fake_edm: Edm) -> None:
    res_stable = fake_edm.wait_for("stable", timeout_s=1.0)
    assert res_stable.payload["ok"] is True

    res_win = fake_edm.wait_for("window", query="exe:fake.exe", timeout_s=1.0)
    assert res_win.payload["ok"] is True

    with pytest.raises(EdmError) as exc_info:
        fake_edm.wait_for("window_gone", query="exe:fake.exe", timeout_s=0.1)
    assert exc_info.value.code == ErrorCode.TIMEOUT

    with pytest.raises(EdmError) as exc_text:
        fake_edm.wait_for("text", query="Tamam", timeout_s=1.0)
    assert exc_text.value.code == ErrorCode.DEPENDENCY_MISSING
