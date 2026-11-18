# Security & Privacy Policy (`edm-desktop`)

## 1. Threat Model & Privacy Boundary

EDM grants an AI agent visual read access and mouse/keyboard write access to your interactive Windows desktop session.

- **Screen & Clipboard Exposure:** Any window, notification, or clipboard text visible during `screenshot`, `zoom`, `ui_elements`, `find_text`, or `clipboard` calls is returned to the connected MCP client or CLI caller.
- **Local-Only Storage:** Observations (`observations/YYYY-MM-DD/*.png`), index (`index.jsonl`), and action audit logs (`logs/actions-YYYY-MM-DD.jsonl`) are written exclusively under `%LOCALAPPDATA%\EDM\` (or `EDM_DATA_DIR`). Automatic retention pruning removes files older than 7 days or exceeding 2 GB.
- **Zero Telemetry / Zero Outbound Network:** EDM makes no outbound network requests and collects no telemetry.

## 2. Emergency Stop (Kill Switch)

You can abort any running EDM action, drag, path drawing, or multi-step sequence immediately at any time:

1. **Global Hotkey:** Press **`Ctrl + Alt + Shift + F12`**.
2. **Named Win32 Event:** Signal the manual-reset event **`Local\EDM_ABORT`**.
3. **Failsafe Corner:** Slam the physical mouse cursor into the top-left corner **`(0, 0)`** (`±1 px`) of the primary monitor (enabled by default via `failsafe_corner = true`).

When triggered, EDM immediately aborts with `ABORTED_BY_USER` (`retryable: false`) and calls `release_held()` to release any held mouse buttons or modifier keys.

## 3. Input & Session Safety Guards

Before every input injection, `Guard.preflight` enforces:

1. **Desktop Session Isolation:** EDM refuses to inject input if the process is running on an isolated desktop (`WinSta0\exebox-...` → `ISOLATED_DESKTOP`), UAC prompt (`Winlogon` → `SECURE_DESKTOP`), or locked session (`SESSION_LOCKED`). EDM **never** calls `SwitchDesktop`, `SetThreadDesktop`, or `OpenDesktopW` to bypass desktop boundaries.
2. **UIPI (User Interface Privilege Isolation):** EDM queries the mandatory integrity level of the target window's process (`process_integrity`). If the target has higher integrity than EDM (or unreadable integrity from a `medium` process), EDM aborts with `ELEVATION_REQUIRED` rather than allowing silent `SendInput` drops.
3. **Stale Observation Guard:** Window observations verify that the target window's bounds, title, and active modal popup (`GetLastActivePopup`) have not changed, and (when `verify=true`) that the 24×24 pixel patch around the target point differs by `<= 0.15` (`STALE_OBSERVATION`).
4. **Cross-Agent Mutual Exclusion:** All actions acquire the named mutex `Local\EDM_INPUT_LOCK` (timeout 10 s → `BUSY`) so concurrent agents cannot interleave mouse or keyboard events.

## 4. Loopback HTTP Mode (`edm serve-http`)

- Binds strictly to `127.0.0.1` or `::1`; non-loopback bind addresses (`0.0.0.0`, LAN IPs) are rejected with `INVALID_ARGUMENT`.
- Requires an `Authorization: Bearer <token>` header validated in constant time (`secrets.compare_digest`) against `%APPDATA%\EDM\http-token` (generated with `secrets.token_urlsafe(32)`).
- Rejects any request carrying a non-loopback browser `Origin` header with HTTP `403 Forbidden` to prevent DNS rebinding and cross-site request attacks from browser tabs.
