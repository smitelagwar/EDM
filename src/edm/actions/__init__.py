"""Desktop input actions, safety guard, and kill switch."""

from edm.actions import clipboard
from edm.actions.keys import (
    KeyEvent,
    chord_events,
    key_state_events,
    parse_chord,
    unicode_events,
)
from edm.actions.mouse import (
    MouseEvent,
    click_events,
    interpolate_path,
    mouse_button_events,
    normalize_abs,
    wheel_events,
)

__all__ = [
    "KeyEvent",
    "MouseEvent",
    "chord_events",
    "click_events",
    "clipboard",
    "interpolate_path",
    "key_state_events",
    "mouse_button_events",
    "normalize_abs",
    "parse_chord",
    "unicode_events",
    "wheel_events",
]
