from __future__ import annotations

import pytest

from edm.actions.sequence import Step
from edm.errors import EdmError, ErrorCode
from edm.service import Edm


def test_sequence_validates_all_first(fake_edm: Edm) -> None:
    shot = fake_edm.screenshot(target="screen")
    obs_id = shot.payload["observation"]["id"]

    steps = [
        Step("click", {"observation_id": obs_id, "x": 156.25, "y": 156.25}),
        Step("type_text", {"text": "hello"}),
        Step("unknown_tool", {}),
    ]
    with pytest.raises(EdmError) as exc_info:
        fake_edm.run_sequence(steps)
    assert exc_info.value.code == ErrorCode.INVALID_ARGUMENT
    assert fake_edm.input_sink.events == []


def test_sequence_max_25(fake_edm: Edm) -> None:
    steps = [Step("type_text", {"text": "a"}) for _ in range(26)]
    with pytest.raises(EdmError) as exc_info:
        fake_edm.run_sequence(steps)
    assert exc_info.value.code == ErrorCode.INVALID_ARGUMENT
    assert fake_edm.input_sink.events == []


def test_sequence_stops_on_error(fake_edm: Edm) -> None:
    steps = [
        Step("type_text", {"text": "ok"}),
        Step("click", {"observation_id": "o-missing", "x": 10, "y": 10}),
        Step("type_text", {"text": "never"}),
    ]
    # Pre-validation catches o-missing before any event is sent!
    with pytest.raises(EdmError) as exc_info:
        fake_edm.run_sequence(steps, stop_on_error=True)
    assert exc_info.value.code == ErrorCode.OBSERVATION_NOT_FOUND
    assert fake_edm.input_sink.events == []

    # Runtime error mid-sequence (2nd step fails at runtime)
    orig_send = fake_edm.input_sink.send
    call_n = 0

    def _fail_second(events):  # type: ignore[no-untyped-def]
        nonlocal call_n
        call_n += 1
        if call_n == 2:
            raise EdmError(ErrorCode.INPUT_BLOCKED, "blocked at step 2")
        return orig_send(events)

    fake_edm.input_sink.send = _fail_second  # type: ignore[method-assign]
    res = fake_edm.run_sequence(
        [
            Step("type_text", {"text": "a"}),
            Step("type_text", {"text": "b"}),
            Step("type_text", {"text": "c"}),
        ],
        stop_on_error=True,
    )
    assert res.payload["ok"] is False
    assert res.payload["error"]["code"] == "INPUT_BLOCKED"
    assert res.payload["details"]["completed"] == 1
    assert len(res.payload["details"]["steps"]) == 2


def test_sequence_continue_when_flag_false(fake_edm: Edm) -> None:
    orig_send = fake_edm.input_sink.send
    call_n = 0

    def _fail_second(events):  # type: ignore[no-untyped-def]
        nonlocal call_n
        call_n += 1
        if call_n == 2:
            raise EdmError(ErrorCode.INPUT_BLOCKED, "blocked at step 2")
        return orig_send(events)

    fake_edm.input_sink.send = _fail_second  # type: ignore[method-assign]
    res = fake_edm.run_sequence(
        [
            Step("type_text", {"text": "a"}),
            Step("type_text", {"text": "b"}),
            Step("type_text", {"text": "c"}),
        ],
        stop_on_error=False,
    )
    assert res.payload["details"]["completed"] == 2
    assert len(res.payload["details"]["steps"]) == 3
    assert res.payload["details"]["steps"][1]["ok"] is False
    assert res.payload["details"]["steps"][2]["ok"] is True


def test_sequence_aborts_on_killswitch_midway(fake_edm: Edm) -> None:
    orig_send = fake_edm.input_sink.send
    call_n = 0

    def _abort_after_two(events):  # type: ignore[no-untyped-def]
        nonlocal call_n
        res = orig_send(events)
        call_n += 1
        if call_n == 2:
            fake_edm.killswitch.signal()
        return res

    fake_edm.input_sink.send = _abort_after_two  # type: ignore[method-assign]
    res = fake_edm.run_sequence(
        [
            Step("type_text", {"text": "1"}),
            Step("type_text", {"text": "2"}),
            Step("type_text", {"text": "3"}),
            Step("type_text", {"text": "4"}),
        ],
        stop_on_error=False,
    )
    assert res.payload["ok"] is False
    assert res.payload["error"]["code"] == "ABORTED_BY_USER"
    assert res.payload["details"]["completed"] == 2
    assert len(res.payload["details"]["steps"]) == 3
