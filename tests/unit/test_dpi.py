from edm.win32 import api
from edm.win32.dpi import ensure_dpi_awareness


def test_dpi_idempotent() -> None:
    first = ensure_dpi_awareness()
    second = ensure_dpi_awareness()
    assert first == "per_monitor_v2" or first.startswith("already_set:")
    assert second.startswith("already_set:") or second == "per_monitor_v2"


def test_api_symbols_bound() -> None:
    assert callable(api.SendInput)
    assert callable(api.GetWindowRect)
    assert callable(api.DwmGetWindowAttribute)
    assert callable(api.GetDpiForMonitor)
    assert callable(api.SetProcessDpiAwarenessContext)
    assert callable(api.GetThreadDpiAwarenessContext)
    assert callable(api.GetAwarenessFromDpiAwarenessContext)
    assert callable(api.IsProcessDPIAware)
