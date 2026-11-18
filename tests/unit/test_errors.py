from edm.errors import NEXT_STEP, RETRYABLE, EdmError, ErrorCode


def test_every_code_has_retryable_and_next_step() -> None:
    codes = list(ErrorCode)
    assert len(codes) == 20
    for code in codes:
        assert code in RETRYABLE
        assert isinstance(RETRYABLE[code], bool)
        assert code in NEXT_STEP
        assert isinstance(NEXT_STEP[code], str)
        assert len(NEXT_STEP[code].strip()) > 0


def test_payload_shape() -> None:
    err = EdmError(
        ErrorCode.STALE_OBSERVATION,
        "Window moved since observation",
        details={"hwnd": 123},
    )
    payload = err.to_payload()
    assert payload == {
        "ok": False,
        "error": {
            "code": "STALE_OBSERVATION",
            "message": "Window moved since observation",
            "retryable": True,
            "next_step": NEXT_STEP[ErrorCode.STALE_OBSERVATION],
            "details": {"hwnd": 123},
        },
    }


def test_payload_default_details() -> None:
    err = EdmError(ErrorCode.ISOLATED_DESKTOP, "Not on interactive desktop")
    payload = err.to_payload()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "ISOLATED_DESKTOP"
    assert payload["error"]["retryable"] is False
    assert "MCP" in payload["error"]["next_step"]
    assert payload["error"]["details"] == {}
