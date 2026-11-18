# Changelog

All notable changes to `edm-desktop` are documented in this file.

## [0.1.0-rc1] - 2026-11-18

### Added
- **Core & Win32 (`Faz 0–1`):**
  - 20 canonical `ErrorCode` values with structured `RETRYABLE` / `NEXT_STEP` agent envelopes and TOML configuration loader (`edm.errors`, `edm.config`).
  - Explicit 64-bit Win32 `ctypes` bindings, idempotent Per-Monitor-V2 DPI awareness (`ensure_dpi_awareness`), desktop session classification (`ok`, `isolated_desktop`, `secure_desktop`, `session_locked`), physical coordinate geometry, bidirectional `ImageMapping` (`pixel` + `norm1000`, chained `zoom`), monitor enumeration, window queries, process integrity (`Integrity`), Turkish case folding (`tr_fold`), and `edm doctor`.
- **Capture & Observation Store (`Faz 2`):**
  - Primary GDI (`mss`) capture backend, blank-frame detector (`is_blank`), 7×7 grid window occlusion estimator (`visible_fraction`), Windows Graphics Capture (`windows-capture`) backend with Win10 `draw_border` fallback, and `PrintWindow(PW_RENDERFULLCONTENT)` backend with DWM frame crop alignment.
  - Disk-backed `ObservationStore` (`%LOCALAPPDATA%\EDM`, 7-day / 2 GB retention pruning), Lanczos preview scaling, lossless-first PNG→JPEG encoding, coordinate grid, cursor crosshair, Set-of-Mark overlays, and `screenshot`/`zoom`/`list_monitors`/`list_windows` tools.
- **Actions & Safety (`Faz 3`):**
  - Keyboard chord parser (`VkKeyScanW`), UTF-16LE surrogate `KEYEVENTF_UNICODE` generator, linear + Catmull-Rom path interpolation (`interpolate_path`), `Win32InputSink` with `release_held()` cleanup.
  - Safety `Guard` (session, `KillSwitch`, UIPI integrity check, re-entrant cross-process `Local\EDM_INPUT_LOCK` mutex) and `KillSwitch` (`Ctrl+Alt+Shift+F12` hotkey thread, `Local\EDM_ABORT` named event, `(0,0)` failsafe corner).
  - Unified `Address` resolution (`obs+xy`, `obs+mark`, `text`, `screen_xy`), 24×24 pixel stale patch & popup verification (`check_stale`), screen settle detection (`wait_for_stable`), mouse/keyboard tools (`click`, `move_mouse`, `drag`, `draw_path`, `mouse_button`, `key_state`, `scroll`, `type_text`, `press_keys`), `window_action`, `launch`, `wait_for`, `clipboard`, and pre-validated `run_sequence`.
- **Perception & Snip (`Faz 4`):**
  - Threaded UIA element collector (`collect_elements`) with 5 s timeout and partial truncation support (`ui_elements`).
  - Offline Windows WinRT OCR (`find_text`, `tr-TR` selection, 2× small-image upscaling, Turkish folding).
  - Fullscreen borderless Tk region selector (`edm snip` / `request_user_region`, `get_user_snips`).
- **Interfaces & Acceptance (`Faz 5–6`):**
  - Complete CLI (`edm`) with JSON output, 90 s watchdog timer, and structured exit codes (`0`, `1`, `2`).
  - MCP `stdio` server (`edm mcp`) and user-started loopback Streamable HTTP server (`edm serve-http`) exposing all 23 tools.
  - Client setup guides (`antigravity`, `codex`, `claude-code`, `gemini-cli`), `scripts/install.ps1`, `integrations/skills/edm-desktop/SKILL.md`, `scripts/run-live-acceptance.ps1`, and application notes (`autocad`, `winrar`, `chrome`, `g-menu`).
