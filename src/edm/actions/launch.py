"""Application target resolution and ShellExecuteExW launcher."""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from edm.errors import EdmError, ErrorCode
from edm.perception.textnorm import tr_fold

_SEE_MASK_NOCLOSEPROCESS = 0x00000040
_SW_SHOWNORMAL = 1


class _SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", wintypes.ULONG),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIconOrMonitor", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


_shell32 = ctypes.WinDLL("shell32", use_last_error=True)
_ShellExecuteExW = _shell32.ShellExecuteExW
_ShellExecuteExW.argtypes = [ctypes.POINTER(_SHELLEXECUTEINFOW)]
_ShellExecuteExW.restype = wintypes.BOOL


@dataclass(frozen=True)
class LaunchSpec:
    """Resolved launch target specification."""

    kind: Literal["path", "shortcut", "aumid", "url"]
    value: str


def default_start_menu_dirs() -> list[Path]:
    """Return user and machine Start Menu Programs directories."""
    dirs: list[Path] = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        dirs.append(Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    progdata = os.environ.get("PROGRAMDATA")
    if progdata:
        dirs.append(Path(progdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    return dirs


def default_aumid_lookup(query: str) -> str | None:
    """Look up a Windows Store / StartApp AUMID matching *query* via ``Get-StartApps``."""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-StartApps | ConvertTo-Json"],
            capture_output=True,
            text=True,
            timeout=5.0,
            check=False,
        )
    except Exception:
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        raw = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    items = raw if isinstance(raw, list) else [raw]
    folded_q = tr_fold(query)
    matches: list[tuple[int, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("Name") or "")
        app_id = str(item.get("AppID") or "")
        if name and app_id and folded_q in tr_fold(name):
            matches.append((len(name), app_id))
    if not matches:
        return None
    matches.sort(key=lambda pair: pair[0])
    return matches[0][1]


def resolve_launch_target(
    target: str,
    start_menu_dirs: list[Path] | None = None,
    aumid_lookup: Callable[[str], str | None] | None = None,
) -> LaunchSpec:
    """Resolve *target* into a ``LaunchSpec`` (path, url, shortcut, or aumid)."""
    stripped = target.strip()
    if not stripped:
        raise EdmError(ErrorCode.INVALID_ARGUMENT, "Launch target must not be empty.")

    lowered = stripped.lower()
    if lowered.startswith(("http://", "https://")):
        return LaunchSpec(kind="url", value=stripped)

    candidate_path = Path(stripped)
    if candidate_path.exists():
        return LaunchSpec(kind="path", value=str(candidate_path))

    dirs = default_start_menu_dirs() if start_menu_dirs is None else start_menu_dirs
    folded_q = tr_fold(stripped)
    shortcuts: list[tuple[int, Path]] = []
    for root in dirs:
        if not root.is_dir():
            continue
        for lnk in root.rglob("*.lnk"):
            if folded_q in tr_fold(lnk.stem):
                shortcuts.append((len(lnk.stem), lnk))
    if shortcuts:
        shortcuts.sort(key=lambda pair: pair[0])
        return LaunchSpec(kind="shortcut", value=str(shortcuts[0][1]))

    lookup = default_aumid_lookup if aumid_lookup is None else aumid_lookup
    aumid = lookup(stripped)
    if aumid:
        return LaunchSpec(kind="aumid", value=aumid)

    raise EdmError(
        ErrorCode.WINDOW_NOT_FOUND,
        f"uygulama bulunamadı: {stripped}",
        details={"target": stripped},
    )


def shell_execute(spec: LaunchSpec, args: list[str] | None = None) -> None:
    """Launch *spec* using ``ShellExecuteExW``."""
    file_arg = f"shell:AppsFolder\\{spec.value}" if spec.kind == "aumid" else spec.value
    params = subprocess.list2cmdline(args) if args else None

    sei = _SHELLEXECUTEINFOW()
    sei.cbSize = ctypes.sizeof(_SHELLEXECUTEINFOW)
    sei.fMask = _SEE_MASK_NOCLOSEPROCESS
    sei.lpVerb = "open"
    sei.lpFile = file_arg
    sei.lpParameters = params
    sei.nShow = _SW_SHOWNORMAL

    if not _ShellExecuteExW(ctypes.byref(sei)):
        err = ctypes.get_last_error()
        raise EdmError(
            ErrorCode.INTERNAL,
            f"ShellExecuteExW failed for {file_arg!r} (win32 error {err}).",
            details={"target": file_arg, "win32_error": err},
        )
    if sei.hProcess:
        ctypes.windll.kernel32.CloseHandle(sei.hProcess)
