from edm.actions.keys import key_state_events
from edm.actions.mouse import (
    MOUSEEVENTF_HWHEEL,
    MOUSEEVENTF_LEFTDOWN,
    MOUSEEVENTF_WHEEL,
    interpolate_path,
    mouse_button_events,
    normalize_abs,
    wheel_events,
)
from edm.fakes import FakeInputSink
from edm.geometry import Point, Rect


def test_normalize_abs_negative_virtual() -> None:
    virt = Rect(-1920, 0, 2560, 1440)
    assert normalize_abs(Point(-1920, 0), virt) == (0, 0)
    assert normalize_abs(Point(2559, 1439), virt) == (65535, 65535)


def test_wheel_events_sign() -> None:
    up = wheel_events(2, 0)
    assert len(up) == 1
    assert up[0].flags == MOUSEEVENTF_WHEEL
    assert up[0].data == 240

    down = wheel_events(-1, 1)
    assert len(down) == 2
    assert down[0].flags == MOUSEEVENTF_WHEEL and down[0].data == -120
    assert down[1].flags == MOUSEEVENTF_HWHEEL and down[1].data == 120


def test_interpolate_path_linear_and_smooth() -> None:
    pts = [Point(0, 0), Point(100, 0), Point(100, 100)]
    lin = interpolate_path(pts, smooth=False, steps_per_segment=4)
    assert lin[0] == Point(0, 0)
    assert lin[-1] == Point(100, 100)
    assert len(lin) >= 7

    sm = interpolate_path(pts, smooth=True, steps_per_segment=4)
    assert sm[0] == Point(0, 0)
    assert sm[-1] == Point(100, 100)
    assert len(sm) >= 7


def test_release_held_clears_down_states() -> None:
    sink = FakeInputSink()
    sink.send(key_state_events(0x11, "down"))
    sink.send(mouse_button_events("left", "down"))
    assert 0x11 in sink.held_vks
    assert "left" in sink.held_buttons

    sink.release_held()
    assert len(sink.held_vks) == 0
    assert len(sink.held_buttons) == 0
    assert any(
        isinstance(ev, dict)
        and ev.get("type") == "mouse"
        and ev.get("flags") != MOUSEEVENTF_LEFTDOWN
        for ev in sink.events
    )
