# EDM — Everything Desktop on Me

> High-resolution Windows desktop vision, region snipping, zoom, UIA/OCR perception, and full mouse/keyboard control for AI agents via **MCP** and **CLI**.

> **Status:** Planning & architecture complete (`v0.1` specification ready). Source implementation begins at [Phase 0](docs/plan/01-UYGULAMA-PLANI.md).  
> **Türkçe:** [README.tr.md](README.tr.md) · **Design & Plan:** [docs/plan/00-TASARIM.md](docs/plan/00-TASARIM.md)

---

## Why EDM Exists

AI agents trying to drive real Windows desktop apps (AutoCAD, WinRAR, Chrome dialogs, AOC G-Menu, etc.) repeatedly fail on the first attempt and loop because:
1. **Fragile window binding:** Window-scoped capture (`WGC` / `PrintWindow`) times out or returns blank frames on DirectX/OpenGL viewports, splash screens, popups, or system tray menus.
2. **UI Automation blind spots:** Standard controls expose accessibility trees, while CAD viewports and custom hardware UIs appear as opaque black boxes.
3. **DPI & coordinate drift:** Scaled monitors (125% / 150% / 4K) cause pixel guesses to miss small toolbar icons.
4. **Silent OS blocks (UIPI & isolated desktops):** Elevated apps silently drop standard `SendInput`, and sandboxed agent shells run on an isolated desktop (`WinSta0\exebox-...`) instead of the user's visible `WinSta0\Default` session.

**EDM solves this with an observation-bound, PrintScreen-first, closed-loop architecture:**
- **See everything actually on screen:** Virtual screen, specific monitor, visible window crop (GDI composite), or rectangular region — with WGC and `PrintWindow` fallbacks for occluded windows and blank-frame detection.
- **Coarse-to-fine `zoom`:** Inspect full-screen layout, then crop/zoom any dense ribbon or tiny button at native pixel resolution (preserving lossless PNG on small CAD crops) while EDM automatically maps coordinates back to the physical virtual screen (`pixel` or `norm1000`).
- **Human-like full input & drawing control:** Single/double/right/middle clicks, straight drags, smooth multi-point continuous strokes (`draw_path` for Paint/CAD curves), held buttons/keys (`mouse_button`, `key_state` with automatic release-on-error), Unicode typing, shortcuts, and validated multi-step sequences.
- **Closed-loop safety:** Per-Monitor-V2 DPI lock, UIPI elevation detection (`ELEVATION_REQUIRED`), stale-observation guard (window geometry + 24×24 pixel patch verification), inter-agent input lock, and instant global kill switch (`Ctrl+Alt+Shift+F12` + `(0,0)` corner).
- **Multi-client ready:** One core engine (`src/edm`) exposed as both an **MCP server** (`stdio` + user-started loopback HTTP) and a JSON **CLI** (`edm`), designed for Antigravity, Codex Desktop, Claude Code, Gemini CLI (`agy`), and local scripts.

---

## Planned Architecture (v0.1)

```text
AI Clients (Antigravity / Codex / Claude Code / Gemini CLI)  ──MCP──▶  mcp_server.py / http_server.py
User / Local Scripts                                        ──CLI──▶  cli.py
                                                                          │
                                                                    service.Edm (single facade)
                                                                          │
    ┌──────────────────────┬──────────────────────┬───────────────────────┴──────────────────────┐
    ▼                      ▼                      ▼                                              ▼
capture/                observe/              perception/                                    actions/
gdi → wgc → pw         store, render, diff    uia (SoM), winrt ocr (tr-TR)                  guard, killswitch, input
```

Key design & planning documents (in Turkish):
- [docs/plan/00-TASARIM.md](docs/plan/00-TASARIM.md) — System design, coordinate contract, 20 MCP tools, error taxonomy.
- [docs/plan/01-UYGULAMA-PLANI.md](docs/plan/01-UYGULAMA-PLANI.md) — TDD task-by-task implementation plan (Phases 0–6).
- [docs/plan/02-TEST-VE-KABUL.md](docs/plan/02-TEST-VE-KABUL.md) — Automated gates, live acceptance suite (`L1–L11`), and real app matrix (`M1–M7`).
- [docs/plan/PROGRESS.md](docs/plan/PROGRESS.md) — Live execution tracker.
- [AGENTS.md](AGENTS.md) — Strict agent start/stop, anti-loop, and safety rules.

---

## Security & Privacy Model

- **Local-only:** No cloud telemetry or outbound network calls. Screenshots and action logs stay strictly under `%LOCALAPPDATA%\EDM\` (auto-pruned at 7 days / 2 GB) and are **never committed to Git**.
- **Explicit boundaries:** EDM never switches Windows desktops, patches sandboxes, or bypasses UAC. If an elevated app (e.g., G-Menu) requires admin integrity, EDM detects it and asks the user to launch EDM elevated if desired.
- **Screenshot sensitivity:** Anything visible on your screen when a tool runs can be sent as tool output to whichever AI client invoked EDM. Do not leave secrets or banking sessions uncovered during agent runs.

---

## Acknowledgments & Prior Art

EDM is written cleanly from scratch for Windows, informed by lessons from open-source GUI agents and local Windows automation work; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## License

[MIT](LICENSE) © 2026 Hüseyin Günaydın
