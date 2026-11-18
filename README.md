# EDM — Everything Desktop on Me

> [Türkçe Dokümantasyon (`README.tr.md`)](README.tr.md)

**EDM (`edm-desktop`)** gives AI coding and automation agents high-resolution Windows desktop vision (screen, monitor, window, region, chained zoom, UI Automation Set-of-Mark, offline Windows OCR, and user-drawn region snips) and human-like mouse/keyboard/drawing control over **MCP (`stdio` + loopback Streamable HTTP)** and **CLI**.

## What It Does

- **Observation-Bound Coordinate Contract:** Every capture returns an `observation_id` with exact preview-to-screen mapping (`pixel` and `norm1000` `[0..1000]` spaces) and Per-Monitor-V2 DPI awareness (`±1 px`).
- **Multi-Backend Capture:** Primary GDI (`mss`) composite capture with automatic occlusion detection (`visible_fraction < 0.98`) and blank-frame fallback to Windows Graphics Capture (`windows-capture`) and `PrintWindow(PW_RENDERFULLCONTENT)`.
- **Offline Perception:** Numbered UI Automation (`ui_elements` Set-of-Mark with 5 s timeout) and offline Windows WinRT OCR (`find_text` with Turkish `İ/I` case folding and automatic 2× upscaling for small crops).
- **Human-Like Input & Safety:** `click`, `move_mouse`, `drag` (20 intermediate steps), `draw_path` (up to 200 points with optional Catmull-Rom spline smoothing for CAD/brush work), `mouse_button`, `key_state`, `scroll`, `type_text` (`KEYEVENTF_UNICODE`), `press_keys` (`VkKeyScanW`), `window_action`, `launch`, `wait_for`, `clipboard`, and `run_sequence`.
- **Fail-Fast Guards:** Session/desktop classification (`ISOLATED_DESKTOP`, `SECURE_DESKTOP`, `SESSION_LOCKED`), UIPI process integrity check (`ELEVATION_REQUIRED`), observation TTL + window move/popup + 24×24 pixel patch verification (`STALE_OBSERVATION`), cross-agent `Local\EDM_INPUT_LOCK`, and emergency abort (`Ctrl+Alt+Shift+F12` / `Local\EDM_ABORT` / `(0,0)` corner).

## Quick Install (3 Commands)

```powershell
git clone https://github.com/smitelagwar/EDM.git C:\Users\hsyn\Desktop\EDM
uv tool install --editable C:\Users\hsyn\Desktop\EDM
edm doctor
```

## Client Integration Guides

- [Antigravity (`docs/integrations/antigravity.md`)](docs/integrations/antigravity.md)
- [Codex Desktop / CLI (`docs/integrations/codex.md`)](docs/integrations/codex.md)
- [Claude Code (`docs/integrations/claude-code.md`)](docs/integrations/claude-code.md)
- [Gemini CLI (`docs/integrations/gemini-cli.md`)](docs/integrations/gemini-cli.md)
- [Agent Skill (`integrations/skills/edm-desktop/SKILL.md`)](integrations/skills/edm-desktop/SKILL.md)

## MCP Tools (23) & CLI Commands

| MCP Tool (`edm`) | CLI Subcommand | Description |
|---|---|---|
| `doctor` | `edm doctor` | Environment, desktop session (`WinSta0\Default` vs `exebox`), DPI, monitors, and backends |
| `list_monitors` | `edm monitors` | Physical display monitors, DPI, and work areas |
| `list_windows` | `edm windows [--query Q]` | Visible top-level windows in Z-order |
| `screenshot` | `edm shot --target T` | Capture `screen`, `monitor:N`, `window:Q`, or `region:x,y,w,h` |
| `zoom` | `edm zoom --obs ID --x X --y Y --w W --h H` | Magnify sub-region up to 4× (lossless PNG first) |
| `ui_elements` | `edm elements [--window Q]` | Interactive UIA controls + Set-of-Mark preview |
| `find_text` | `edm find-text QUERY` | Offline Windows OCR search (`contains`, `exact`, `regex`) |
| `click` | `edm click --obs ID --x X --y Y` | Addressable click (`obs+xy`, `obs+mark`, `text`, or `screen`) |
| `move_mouse` | `edm move ...` | Move cursor to addressed point |
| `drag` | `edm drag --from-... --to-...` | Smooth 20-step drag between two addresses |
| `draw_path` | `edm draw-path --obs ID --points JSON` | Continuous multi-point stroke (up to 200 points, optional Catmull-Rom) |
| `mouse_button` | `edm mouse-btn down\|up` | Hold or release a mouse button (`left`, `right`, `middle`) |
| `key_state` | `edm key-state KEY down\|up` | Hold or release a single key |
| `scroll` | `edm scroll --dy N` | Vertical/horizontal wheel scroll at target |
| `type_text` | `edm type --text "..."` | Layout-independent Unicode typing (`KEYEVENTF_UNICODE`) |
| `press_keys` | `edm keys ctrl+s` | Keyboard shortcut chords (`VkKeyScanW` aware) |
| `window_action` | `edm window Q ACTION` | `focus`, `minimize`, `maximize`, `restore`, `close`, `move`, `resize` |
| `launch` | `edm launch TARGET` | Launch path, Start Menu `.lnk`, AUMID, or URL |
| `wait_for` | `edm wait KIND` | Wait (≤60 s) for `change`, `stable`, `window`, `window_gone`, or `text` |
| `clipboard` | `edm clip get\|set` | Read or write Windows clipboard text/image |
| `run_sequence` | `edm seq --steps JSON` | Pre-validated batch (≤25 steps) under single input lock |
| `request_user_region` | `edm snip [--prompt P]` | Freeze screen for user-drawn region selection (`user_snip`) |
| `get_user_snips` | `edm snip --list` | Retrieve recent user-snipped observations |
| — | `edm prune` | Prune observations older than 7 days or > 2 GB |
| — | `edm mcp` | Run MCP stdio server |
| — | `edm serve-http` | Run user-started loopback (`127.0.0.1`/`::1`) Streamable HTTP MCP server |

## Security & Privacy Notice

- **Everything visible on your screen or clipboard can be sent to the connected AI client/LLM** when you invoke capture or clipboard tools. Close sensitive documents, passwords, and tokens before granting desktop access.
- All captured observations and action logs are stored strictly under `%LOCALAPPDATA%\EDM\` (`EDM_DATA_DIR`) with automatic 7-day / 2 GB retention pruning and are **never** written to the repository.
- Loopback HTTP mode (`edm serve-http`) binds only to `127.0.0.1` or `::1`, requires a 32-byte Bearer token (`%APPDATA%\EDM\http-token`), and rejects non-loopback browser `Origin` headers with HTTP `403`.
- See [SECURITY.md](SECURITY.md) for the full threat model and emergency kill switch details.

## Known Limitations

- **Windows 10/11 only** (`sys.platform == "win32"`, Python `>=3.12,<3.14`).
- **Secure desktop & DRM:** UAC prompts (`Winlogon`), the Windows lock screen, DRM-protected media, and windows using `WDA_EXCLUDEFROMCAPTURE` cannot be captured by user-mode processes; EDM explicitly reports `SECURE_DESKTOP`, `SESSION_LOCKED`, or `CAPTURE_BLANK`.
- **Elevated windows (UIPI):** An unprivileged (`medium` integrity) EDM process cannot inject input into an Administrator (`high` integrity) window; EDM reports `ELEVATION_REQUIRED`.
- **Windows 10 WGC yellow border:** On Windows 10 builds `< 22000`, `windows-capture` fallback may briefly show the OS yellow capture border.

## License

Released under the [MIT License](LICENSE). Third-party acknowledgments are documented in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
