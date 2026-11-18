# Third-Party Notices and Architectural Inspirations

EDM is an original clean-room implementation written for Windows. No source code is copied from third-party repositories unless explicitly attributed here with a compatible license (MIT, BSD, or Apache-2.0).

## Architectural Inspirations Studied During Planning

- **Windows MCP & UIA/DOM hybrids:**
  - `CursorTouch/Windows-MCP` — https://github.com/CursorTouch/Windows-MCP
  - `sandraschi/windows-computer-use-mcp` — https://github.com/sandraschi/windows-computer-use-mcp
  - `dev-willbird1936/Desktop-Computer-Use` — https://github.com/dev-willbird1936/Desktop-Computer-Use
  - `sbroenne/mcp-windows` — https://github.com/sbroenne/mcp-windows
- **High-resolution CAD grounding, coarse-to-fine zoom & Set-of-Mark:**
  - `likaixin2000/ScreenSpot-Pro-GUI-Grounding` — https://github.com/likaixin2000/ScreenSpot-Pro-GUI-Grounding
  - `Princeton-AI2-Lab/ZoomClick` — https://github.com/Princeton-AI2-Lab/ZoomClick
  - `ZJU-REAL/UI-Zoomer` — https://github.com/ZJU-REAL/UI-Zoomer
  - `microsoft/OmniParser` — https://github.com/microsoft/OmniParser
- **Desktop GUI agent loops, orchestration & sandboxing:**
  - `microsoft/UFO` — https://github.com/microsoft/UFO
  - `simular-ai/Agent-S` — https://github.com/simular-ai/Agent-S
  - `bytedance/UI-TARS-desktop` — https://github.com/bytedance/UI-TARS-desktop
  - `OpenAdaptAI/OpenAdapt` — https://github.com/OpenAdaptAI/OpenAdapt
  - `trycua/cua` — https://github.com/trycua/cua
  - `remorses/usecomputer` — https://github.com/remorses/usecomputer
- **Local prior work by repository owner:**
  - `muhendis-mimar-portali/scripts/idecad/desktop.py` (lessons on `SetProcessDpiAwarenessContext`, stale observation checks, `WindowFromPoint` occlusion checks, and Win32 `SendInput`).
