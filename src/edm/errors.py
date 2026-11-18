"""Structured error model for EDM."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Canonical EDM error codes."""

    ISOLATED_DESKTOP = "ISOLATED_DESKTOP"
    SECURE_DESKTOP = "SECURE_DESKTOP"
    SESSION_LOCKED = "SESSION_LOCKED"
    ELEVATION_REQUIRED = "ELEVATION_REQUIRED"
    WINDOW_NOT_FOUND = "WINDOW_NOT_FOUND"
    WINDOW_MINIMIZED = "WINDOW_MINIMIZED"
    STALE_OBSERVATION = "STALE_OBSERVATION"
    OBSERVATION_NOT_FOUND = "OBSERVATION_NOT_FOUND"
    POINT_OUT_OF_BOUNDS = "POINT_OUT_OF_BOUNDS"
    CAPTURE_FAILED = "CAPTURE_FAILED"
    CAPTURE_BLANK = "CAPTURE_BLANK"
    INPUT_BLOCKED = "INPUT_BLOCKED"
    ABORTED_BY_USER = "ABORTED_BY_USER"
    BUSY = "BUSY"
    TIMEOUT = "TIMEOUT"
    UIA_UNAVAILABLE = "UIA_UNAVAILABLE"
    UIA_TIMEOUT = "UIA_TIMEOUT"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    INTERNAL = "INTERNAL"


RETRYABLE: dict[ErrorCode, bool] = {
    ErrorCode.ISOLATED_DESKTOP: False,
    ErrorCode.SECURE_DESKTOP: False,
    ErrorCode.SESSION_LOCKED: False,
    ErrorCode.ELEVATION_REQUIRED: False,
    ErrorCode.WINDOW_NOT_FOUND: True,
    ErrorCode.WINDOW_MINIMIZED: True,
    ErrorCode.STALE_OBSERVATION: True,
    ErrorCode.OBSERVATION_NOT_FOUND: True,
    ErrorCode.POINT_OUT_OF_BOUNDS: True,
    ErrorCode.CAPTURE_FAILED: True,
    ErrorCode.CAPTURE_BLANK: True,
    ErrorCode.INPUT_BLOCKED: False,
    ErrorCode.ABORTED_BY_USER: False,
    ErrorCode.BUSY: True,
    ErrorCode.TIMEOUT: True,
    ErrorCode.UIA_UNAVAILABLE: False,
    ErrorCode.UIA_TIMEOUT: False,
    ErrorCode.DEPENDENCY_MISSING: False,
    ErrorCode.INVALID_ARGUMENT: True,
    ErrorCode.INTERNAL: False,
}

NEXT_STEP: dict[ErrorCode, str] = {
    ErrorCode.ISOLATED_DESKTOP: (
        "EDM is not on the interactive desktop; inform the user to register EDM as an MCP server "
        "or run edm serve-http, and do not retry."
    ),
    ErrorCode.SECURE_DESKTOP: (
        "A UAC or secure desktop prompt is active; ask the user to resolve it and then call "
        "wait_for stable."
    ),
    ErrorCode.SESSION_LOCKED: (
        "The Windows session is locked; ask the user to unlock it and then call wait_for stable."
    ),
    ErrorCode.ELEVATION_REQUIRED: (
        "The target window is elevated; ask the user to start EDM as Administrator."
    ),
    ErrorCode.WINDOW_NOT_FOUND: (
        "Call list_windows to inspect available windows or launch the target application."
    ),
    ErrorCode.WINDOW_MINIMIZED: (
        "Restore the window with window_action restore or pass restore=true to screenshot."
    ),
    ErrorCode.STALE_OBSERVATION: ("Call screenshot again and retry using the new observation_id."),
    ErrorCode.OBSERVATION_NOT_FOUND: (
        "Call screenshot to capture a fresh observation and use its observation_id."
    ),
    ErrorCode.POINT_OUT_OF_BOUNDS: (
        "Provide coordinates within the bounds of the referenced observation image."
    ),
    ErrorCode.CAPTURE_FAILED: (
        "Retry once with target='screen' or focus the target window before capturing."
    ),
    ErrorCode.CAPTURE_BLANK: ("Focus the target window or retry once with target='screen'."),
    ErrorCode.INPUT_BLOCKED: ("Input was blocked by UIPI or security software; inform the user."),
    ErrorCode.ABORTED_BY_USER: ("Stop immediately and ask the user how to proceed."),
    ErrorCode.BUSY: ("Wait 1 to 2 seconds and retry the operation up to three times."),
    ErrorCode.TIMEOUT: ("Review the wait condition or increase timeout_s and retry once."),
    ErrorCode.UIA_UNAVAILABLE: (
        "Fall back to find_text (OCR) or visual coordinates from screenshot."
    ),
    ErrorCode.UIA_TIMEOUT: ("Fall back to find_text (OCR) or visual coordinates from screenshot."),
    ErrorCode.DEPENDENCY_MISSING: (
        "Inform the user of the missing dependency and installation step in the error message."
    ),
    ErrorCode.INVALID_ARGUMENT: (
        "Fix the invalid argument according to the error message and retry."
    ),
    ErrorCode.INTERNAL: ("Report the unexpected internal error and log path to the user."),
}


class EdmError(Exception):
    """Domain exception carrying a structured EDM error payload."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details: dict[str, Any] = dict(details) if details is not None else {}

    def to_payload(self) -> dict[str, Any]:
        """Serialize the error into the canonical EDM JSON envelope."""
        return {
            "ok": False,
            "error": {
                "code": str(self.code),
                "message": self.message,
                "retryable": RETRYABLE[self.code],
                "next_step": NEXT_STEP[self.code],
                "details": self.details,
            },
        }
