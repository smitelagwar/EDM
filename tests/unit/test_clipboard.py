from edm.actions import clipboard
from edm.service import Edm


def test_clipboard_roundtrip_restores() -> None:
    previous = clipboard.get_text()
    try:
        clipboard.set_text("EDM-TEST-ğ")
        assert clipboard.get_text() == "EDM-TEST-ğ"
    finally:
        if previous is not None:
            clipboard.set_text(previous)


def test_service_clipboard_fake(fake_edm: Edm) -> None:
    set_res = fake_edm.clipboard("set", text="Merhaba ğüşıöç")
    assert set_res.payload["ok"] is True

    get_res = fake_edm.clipboard("get")
    assert get_res.payload["ok"] is True
    assert get_res.payload["text"] == "Merhaba ğüşıöç"
