---
name: edm-desktop
description: Use when inspecting, capturing, or controlling Windows desktop applications (GUI windows, dialogs, CAD viewports, monitors, mouse, keyboard, UIA, OCR) via the EDM MCP server or edm CLI.
---

# EDM (Everything Desktop on Me) — Agent Operating Guide

EDM provides high-resolution Windows desktop vision and human-like mouse/keyboard control with observation-bound coordinates and strict safety guards.

## 1. Mandatory Session Start

1. Call `doctor` **once** at the beginning of the session.
2. Check `session.state`:
   - `"ok"`: proceed normally on the interactive desktop (`WinSta0\Default`).
   - `"isolated_desktop"`: **STOP immediately**. Do not retry, do not call `SwitchDesktop`/`SetThreadDesktop`, and do not start `edm serve-http` yourself. Inform the user to register EDM as an MCP server or start `edm serve-http` in their own interactive session.

## 2. Action Strategy Ladder (Cheapest & Most Reliable First)

Always climb this ladder in order:

1. **Non-visual / Native CLI / Shortcuts first:**
   - Use application CLIs (`rar.exe`, `7z.exe`), keyboard shortcuts (`press_keys("ctrl+s")`), AutoCAD command line, or browser DOM tools before clicking pixels.
2. **UI Automation (Set-of-Mark):**
   - Call `ui_elements(window="...")` → inspect numbered marks → `click(observation_id=..., mark=N)`.
3. **Offline Windows OCR (`tr-TR` aware):**
   - Call `find_text(query="Tamam", target="window:...")` or `click(text="Tamam", target="window:...")`.
4. **Visual Coordinates (`screenshot` + `zoom`):**
   - Call `screenshot(target="window:...")`.
   - For small or dense targets (CAD toolbars, status bar icons), call `zoom(observation_id=..., x=..., y=..., w=..., h=...)` first, then `click(observation_id=zoom_obs_id, x=..., y=...)`.
5. **Continuous Drawing / Orbit / Hold-Release:**
   - Use `draw_path(observation_id=..., points=[[x,y], ...], smooth=True)` for multi-point strokes or CAD polylines.
   - Use `mouse_button` / `key_state` (`down`/`up`) or `run_sequence` for compound interactions.

## 3. Verification & Loop Brake (Strict)

- **Verify every action:** Read the returned post-action `observation` to confirm the expected UI change occurred.
- **2-attempt rule per method:** Try the same step with the same method **at most 2 times**. On the second failure, switch to the next rung on the strategy ladder.
- **3-method cap:** If 3 distinct methods fail, **STOP** and report the final `observation.path` and error payload to the user.
- **Never retry `retryable: false` errors.**

## 4. Error Code → Required Agent Behavior

| Error Code | Retryable | Required Action |
|---|---|---|
| `ISOLATED_DESKTOP` | `false` | Stop immediately; ask user to run EDM on interactive desktop / MCP |
| `SECURE_DESKTOP` / `SESSION_LOCKED` | `false` | Ask user to resolve UAC prompt or unlock screen, then `wait_for("stable")` |
| `ELEVATION_REQUIRED` | `false` | Target window runs as Administrator; ask user to start EDM elevated |
| `ABORTED_BY_USER` | `false` | User triggered kill switch (`Ctrl+Alt+Shift+F12` or `(0,0)` corner); stop and ask user |
| `INPUT_BLOCKED` | `false` | Blocked by UIPI or security software; inform user |
| `UIA_UNAVAILABLE` / `UIA_TIMEOUT` | `false` | Fall back to `find_text` (OCR) or `screenshot` + `zoom` coordinates |
| `DEPENDENCY_MISSING` | `false` | Relay installation instructions from message to user |
| `STALE_OBSERVATION` / `OBSERVATION_NOT_FOUND` | `true` | Take a fresh `screenshot` and use the new `observation_id` |
| `WINDOW_MINIMIZED` | `true` | Call `window_action(..., "restore")` or `screenshot(..., restore=True)` |
| `WINDOW_NOT_FOUND` | `true` | Call `list_windows` or `launch` the application |
| `POINT_OUT_OF_BOUNDS` | `true` | Supply coordinates within the observation's `image_size` |
| `CAPTURE_FAILED` / `CAPTURE_BLANK` | `true` | Focus the window or retry once with `target="screen"` |
| `BUSY` | `true` | Wait 1–2 s and retry up to 3 times |
| `TIMEOUT` | `true` | Review condition or increase `timeout_s` and retry once |
| `INVALID_ARGUMENT` | `true` | Fix parameter syntax/range and retry |

## 5. Application Notes

For application-specific pitfalls and workflows, consult:
- `docs/app-notes/autocad.md` (command line focus, modal dialogs, OSNAP, GPU viewport capture)
- `docs/app-notes/winrar.md` (CLI `rar.exe` preference, UIA dialogs)
- `docs/app-notes/chrome.md` (DOM tools vs native file dialogs)
- `docs/app-notes/gmenu.md` (`ELEVATION_REQUIRED` handling for administrator utilities)
