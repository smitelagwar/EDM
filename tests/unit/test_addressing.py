import pytest

from edm.actions.addressing import Address, resolve_point, validate_address
from edm.errors import EdmError, ErrorCode
from edm.geometry import Point
from edm.service import Edm


def test_validate_address_exactly_one() -> None:
    assert validate_address(Address(observation_id="o-1", x=10, y=20)) == "obs"
    assert validate_address(Address(observation_id="o-1", mark=1)) == "mark"
    assert validate_address(Address(text="OK")) == "text"
    assert validate_address(Address(screen_x=100, screen_y=200)) == "screen"

    invalid = [
        Address(),
        Address(observation_id="o-1"),
        Address(x=10, y=20),
        Address(screen_x=100),
        Address(observation_id="o-1", x=10, y=20, screen_x=1, screen_y=2),
        Address(observation_id="o-1", mark=1, text="OK"),
    ]
    for addr in invalid:
        with pytest.raises(EdmError) as exc_info:
            validate_address(addr)
        assert exc_info.value.code == ErrorCode.INVALID_ARGUMENT


def test_resolve_point_screen_warns(fake_edm: Edm) -> None:
    pt, obs, warnings = resolve_point(fake_edm, Address(screen_x=300, screen_y=400))
    assert pt == Point(300, 400)
    assert obs is None
    assert len(warnings) >= 1


def test_resolve_point_text_dependency_missing(fake_edm: Edm) -> None:
    with pytest.raises(EdmError) as exc_info:
        resolve_point(fake_edm, Address(text="OK"))
    assert exc_info.value.code == ErrorCode.DEPENDENCY_MISSING
