"""Per-Monitor-V2 DPI awareness helper."""

from __future__ import annotations

from edm.win32 import api


def _describe_current_awareness() -> str:
    ctx = api.GetThreadDpiAwarenessContext()
    if ctx:
        if api.AreDpiAwarenessContextsEqual(ctx, api.DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2):
            return "per_monitor_v2"
        awareness = int(api.GetAwarenessFromDpiAwarenessContext(ctx))
        if awareness == api.DPI_AWARENESS_PER_MONITOR_AWARE:
            return "per_monitor"
        if awareness == api.DPI_AWARENESS_SYSTEM_AWARE:
            return "system"
        if awareness == api.DPI_AWARENESS_UNAWARE:
            return "unaware"
    if api.IsProcessDPIAware():
        return "system"
    return "unknown"


def ensure_dpi_awareness() -> str:
    """Enable Per-Monitor-V2 DPI awareness idempotently.

    Returns ``"per_monitor_v2"`` when newly enabled, or
    ``"already_set:<level>"`` when DPI awareness was already configured.
    """
    if api.SetProcessDpiAwarenessContext(api.DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2):
        return "per_monitor_v2"
    return f"already_set:{_describe_current_awareness()}"
