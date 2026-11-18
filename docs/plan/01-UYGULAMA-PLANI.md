# EDM v0.1 Uygulama Planı

> **Ajanlar için:** Önce [AGENTS.md](../../AGENTS.md) okunur (başlangıç/bitiş ve döngü önleme kuralları). Ardından [00-TASARIM.md](00-TASARIM.md) okunur. Görevler sırayla uygulanır ve ilerleme [PROGRESS.md](PROGRESS.md)'de checkbox ile işaretlenir. Tercih edilen yürütme: `superpowers:executing-plans` (aynı oturumda, görev görev). Faz sonlarında bağımsız bir gözden geçirme yapılır.

**Goal:** AI ajanlarına Windows masaüstünde yüksek çözünürlüklü görme (ekran/monitör/pencere/bölge, zoom, UIA, OCR) ve tam fare/klavye kontrolü veren, MCP + CLI arayüzlü `EDM` paketini v0.1 olarak teslim etmek.

**Architecture:** Saf Python çekirdek (`src/edm`). Win32 erişimi ctypes ile yapılır. Tek facade (`service.Edm`) üzerinde iki kabuk vardır: MCP sunucusu (stdio + kullanıcı başlatmalı loopback HTTP) ve CLI. Saf mantık (geometri, eşleme, ayrıştırma, karar) birim testlerle, Win32 yan etkileri sahte (fake) arka uçlarla, gerçek masaüstü ise `live` işaretli testlerle doğrulanır.

**Tech Stack:** Python 3.12 (uv) · `mcp` (resmî SDK, FastMCP) · `mss` · `Pillow` · `comtypes` + `uiautomation` · `windows-capture` (WGC) · `winrt-*` (Windows OCR) · pytest + pytest-timeout + hypothesis · ruff · mypy.

**Spec:** [docs/plan/00-TASARIM.md](00-TASARIM.md) · Test ve kabul: [02-TEST-VE-KABUL.md](02-TEST-VE-KABUL.md)

## Global Constraints

- Python `>=3.12,<3.14`, `.python-version` = `3.12`. Paket adı `edm-desktop`, import adı `edm`, konsol komutu `edm`, MCP sunucu adı `edm`.
- Yalnız Windows. `sys.platform != "win32"` ise `edm` şu mesajla çıkar: `EDM yalnızca Windows'ta çalışır`, kod 2.
- DPI: Her giriş noktası (`cli.main`, `mcp_server.run_*`, `Edm.__init__`) GDI/UIA çağrısından önce `ensure_dpi_awareness()` çağırır (Per-Monitor-V2 = `-4`).
- Tüm iç koordinatlar sanal ekranın fiziksel pikselleridir (negatif olabilir).
- Önizleme uzun kenar varsayılanı 1600 px. Görüntü yük sınırı 1 500 000 bayt. JPEG kalitesi basamakları 85, 75, 60.
- Gözlem ömrü 120 s. Stale yaması 24 px, eşik 0.15. Eylem sonrası durulma: 300 ms sessizlik, en fazla 3000 ms.
- Zaman sınırları: tek araç ≤ 60 s, `wait_for` ≤ 60 s, UIA 5 s, WGC kare 3 s, CLI bekçisi 90 s, pytest varsayılan 60 s (live 120 s).
- Veri: `%LOCALAPPDATA%\EDM\` (`EDM_DATA_DIR` ile değişir). Yapılandırma: `%APPDATA%\EDM\config.toml` (`EDM_CONFIG` ile değişir). Saklama 7 gün / 2 000 000 000 bayt.
- Acil durdurma: `ctrl+alt+shift+f12` + birincil monitör (0,0) köşe güvenliği. Adlı nesneler: `Local\EDM_INPUT_LOCK`, `Local\EDM_ABORT`.
- Yasak: `SwitchDesktop`, `SetThreadDesktop`, `OpenDesktopW(...)` ile masaüstü değiştirme. UAC atlatma. uiAccess hilesi. Ağ çağrısı (loopback HTTP modu hariç). Telemetri.
- Görüntü/günlük dosyaları asla commit edilmez. Kaynak dosyalar UTF-8 (BOM'suz). `.gitattributes`: `* text=auto eol=lf`.
- Commit biçimi Conventional Commits. Her görev = 1 commit. Her faz sonu = `git push origin main`.
- `EDM_FAKE=1` iken `Edm` sahte yakalama, girdi ve oturum kullanır (CI ve izole masaüstü için).

## Review Focus

1. **Karışık DPI (%125/%150):** Önizleme → ekran eşlemesi ±1 px içinde kalmalı. Test: `test_mapping_roundtrip_scaled` (T1.3). Canlı L4/L5 kullanıcıda %125'te tekrar edilir.
2. **Gözlem ile eylem arasında pencere taşındı/kapandı/modal açıldı:** Tıklama gönderilmemeli, `STALE_OBSERVATION` dönmeli. Testler: `test_click_rejects_moved_window`, `test_click_rejects_patch_change` (T3.4). Canlı L9.
3. **Yönetici yetkili hedef (G-Menu):** Sessiz no-op olmamalı, `ELEVATION_REQUIRED` dönmeli. Test: `test_preflight_elevation_required` (T3.2).
4. **UAC/kilit ekranı:** Asılı kalmadan `SECURE_DESKTOP`/`SESSION_LOCKED` dönmeli. Test: `test_classify_session_table` (T1.2) + `test_preflight_secure_desktop` (T3.2).
5. **Türkçe klavye ve Unicode:** `type_text("ğüşıöçİĞÜŞÖÇ €😀")` düzen bağımsız çalışmalı. Kısayol harfleri TR-Q düzeninde `VkKeyScanW` ile çözülmeli. Testler: `test_unicode_events_surrogates`, `test_parse_chord_layout_letter` (T3.1). Canlı L6.
6. **GPU çizimli pencerede siyah kare (AutoCAD görünüm alanı):** Boş kare tespiti yedeğe geçmeli. Test: `test_capturer_falls_back_on_blank` (T2.2).
7. **Yanıt vermeyen uygulamada UIA asılması:** 5 s'de kısmi sonuç dönmeli (`truncated=true`). Test: `test_collect_elements_timeout_partial` (T4.1).

---

## Faz 0 — İskelet ve araç zinciri

### T0.1 Proje iskeleti, CI ve `edm --version`

**Files:** Create `pyproject.toml`, `.python-version`, `src/edm/__init__.py`, `src/edm/__main__.py`, `src/edm/cli.py`, `tests/unit/test_version.py`, `tests/conftest.py`, `.github/workflows/ci.yml` (mevcut `.gitattributes` korunur/doğrulanır)

**Interfaces:** Produces `edm.__version__: str = "0.1.0.dev0"`, `edm.cli.main(argv: list[str] | None = None) -> int`.

- [ ] Komutlar: `uv python install 3.12` · `pyproject.toml` dosyasını doğrudan oluştur (`[build-system]` `hatchling`, `[tool.hatch.build.targets.wheel] packages = ["src/edm"]` — **dikkat:** `uv init --package --name edm-desktop` kullanma, `src/edm_desktop` açar ve mevcut `README.md`'ye takılır) · `uv sync` · `uv add mcp mss pillow comtypes uiautomation` · `uv add --dev pytest pytest-timeout hypothesis ruff mypy`.
- [ ] `pyproject.toml`: `[project.scripts] edm = "edm.cli:main"`. `[tool.pytest.ini_options]`: `testpaths=["tests"]`, `addopts="-q -m 'not live' --timeout=60"`, `markers=["live: gerçek etkileşimli masaüstü gerektirir"]`. Ruff: `line-length=100`, `select=["E","F","I","B","UP","SIM"]`. mypy: `strict=true`, `files=["src/edm"]`, `ignore_missing_imports=true`, `warn_unused_ignores=false`.
- [ ] Test `tests/unit/test_version.py`:
```python
from edm import __version__
from edm.cli import main
def test_version_string(): assert __version__ == "0.1.0.dev0"
def test_cli_version(capsys): assert main(["--version"]) == 0 and "0.1.0.dev0" in capsys.readouterr().out
```
- [ ] Çalıştır: `uv run pytest` → FAIL. Uygula. Çalıştır → PASS.
- [ ] CI (`windows-latest`, Python 3.12, `astral-sh/setup-uv`): `uv sync --frozen` → `uv run ruff check .` → `uv run ruff format --check .` → `uv run mypy` → `uv run pytest` (env `EDM_FAKE=1`).
- [ ] Commit: `chore: scaffold edm-desktop package, tooling and CI`

### T0.2 Hata modeli ve yapılandırma

**Files:** Create `src/edm/errors.py`, `src/edm/config.py`, `tests/unit/test_errors.py`, `tests/unit/test_config.py`

**Interfaces (Produces):**
- `class ErrorCode(StrEnum)`: tasarım §10.3'teki 20 kodun tamamı (`ISOLATED_DESKTOP`, `SECURE_DESKTOP`, `SESSION_LOCKED`, `ELEVATION_REQUIRED`, `WINDOW_NOT_FOUND`, `WINDOW_MINIMIZED`, `STALE_OBSERVATION`, `OBSERVATION_NOT_FOUND`, `POINT_OUT_OF_BOUNDS`, `CAPTURE_FAILED`, `CAPTURE_BLANK`, `INPUT_BLOCKED`, `ABORTED_BY_USER`, `BUSY`, `TIMEOUT`, `UIA_UNAVAILABLE`, `UIA_TIMEOUT`, `DEPENDENCY_MISSING`, `INVALID_ARGUMENT`, `INTERNAL`).
- `RETRYABLE: dict[ErrorCode, bool]`, `NEXT_STEP: dict[ErrorCode, str]` (İngilizce, ajana yönelik tek cümle).
- `class EdmError(Exception)`: `__init__(self, code: ErrorCode, message: str, *, details: dict[str, Any] | None = None)`, `to_payload() -> dict` → `{"ok": False, "error": {"code", "message", "retryable", "next_step", "details"}}`.
- `@dataclass(frozen=True) class Config`: global kısıtlardaki tüm sayılar alan olarak (`preview_max_edge=1600`, `max_image_bytes=1_500_000`, `observation_ttl_s=120`, `stale_patch_px=24`, `stale_threshold=0.15`, `settle_quiet_ms=300`, `settle_timeout_ms=3000`, `retention_days=7`, `retention_bytes=2_000_000_000`, `killswitch_hotkey="ctrl+alt+shift+f12"`, `failsafe_corner=True`, `input_lock_timeout_s=10.0`, `uia_timeout_s=5.0`, `wgc_timeout_s=3.0`, `data_dir: Path`).
- `load_config(path: Path | None = None) -> Config`: TOML'daki bilinmeyen anahtar `EdmError(INVALID_ARGUMENT)` üretir. Tip hatası da aynı hatayı üretir.

- [ ] Testler: `test_every_code_has_retryable_and_next_step` (tüm enum üyeleri iki sözlükte) · `test_payload_shape` · `test_config_defaults` (değerler yukarıdakilerle birebir) · `test_config_toml_override(tmp_path)` (`preview_max_edge = 2000`) · `test_config_unknown_key_rejected` · `test_env_data_dir(monkeypatch)`.
- [ ] FAIL → uygula → PASS → Commit: `feat(core): error model and config loader`

**Faz 0 kapısı:** `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest` yeşil + CI yeşil. Sonra `git push origin main`, PROGRESS güncellenir.

---

## Faz 1 — Win32 temel katman ve `doctor`

### T1.1 ctypes bağları ve DPI

**Files:** Create `src/edm/win32/__init__.py`, `src/edm/win32/api.py`, `src/edm/win32/dpi.py`, `tests/unit/test_dpi.py`

**Interfaces:** `api.py`: user32/kernel32/gdi32/dwmapi/advapi32/shcore prototipleri (`restype`/`argtypes` açık, `use_last_error=True`). `dpi.ensure_dpi_awareness() -> str` ("per_monitor_v2" | "already_set:<değer>"), idempotenttir.

- [ ] Testler: `test_dpi_idempotent` (iki çağrı da istisnasız döner, ikincisi `already_set` veya `per_monitor_v2`) · `test_api_symbols_bound` (`SendInput`, `GetWindowRect`, `DwmGetWindowAttribute`, `GetDpiForMonitor` callable).
- [ ] Not: Fikir kaynağı `C:\Users\hsyn\Desktop\muhendis-mimar-portali\scripts\idecad\desktop.py` (DPI, SendInput, odak deneyimi). Kod kopyalanmaz, yeniden yazılır. O dosyadaki `SetThreadDesktop` yolu EDM'de **yasaktır**.
- [ ] Commit: `feat(win32): ctypes bindings and per-monitor-v2 DPI awareness`

### T1.2 Oturum / masaüstü sınıflandırma

**Files:** Create `src/edm/win32/session.py`, `tests/unit/test_session.py`

**Interfaces:** `SessionState = Literal["ok","isolated_desktop","secure_desktop","session_locked"]` · `@dataclass SessionInfo(station: str, thread_desktop: str, input_desktop: str | None, state: SessionState)` · `classify_session(station: str, thread_desktop: str, input_desktop: str | None, locked: bool = False) -> SessionState` · `get_session() -> SessionInfo` (`GetProcessWindowStation`, `GetThreadDesktop`, `OpenInputDesktop(0, False, DESKTOP_READOBJECTS)`, `GetUserObjectInformationW(UOI_NAME)`. Erişim reddi → `input_desktop=None`. Kilit tespiti `WTSQuerySessionInformationW(WTSSessionInfoEx)` ile yapılır, mümkün değilse `locked=False`). **Masaüstü değiştirme çağrısı yoktur.**

- [ ] Test `test_classify_session_table` (parametrize):

| station | thread | input | locked | beklenen |
|---|---|---|---|---|
| WinSta0 | Default | Default | False | ok |
| WinSta0 | exebox-ABC | Default | False | isolated_desktop |
| WinSta0 | Default | Winlogon | False | secure_desktop |
| WinSta0 | Default | None | False | secure_desktop |
| WinSta0 | Default | Default | True | session_locked |
| Service-0x0-3e7$ | Default | None | False | isolated_desktop |

- [ ] Commit: `feat(win32): session and desktop classification`

### T1.3 Geometri, eşleme ve monitörler

**Files:** Create `src/edm/geometry.py`, `src/edm/win32/monitors.py`, `tests/unit/test_geometry.py`, `tests/unit/test_monitors.py`

**Interfaces:**
- `@dataclass(frozen=True) Point(x: int, y: int)` · `Rect(left, top, right, bottom)` + `width`, `height`, `center -> Point`, `contains(p) -> bool`, `intersection(o) -> Rect | None`, `from_xywh(x, y, w, h) -> Rect`, `as_list() -> list[int]`.
- `CoordSpace = Literal["pixel","norm1000"]`
- `@dataclass(frozen=True) ImageMapping(frame_rect: Rect, crop: Rect, image_size: tuple[int, int])` (`crop` çerçeve-yerel piksel). `to_screen(x: float, y: float, space: CoordSpace = "pixel") -> Point` (dışarıdaysa `EdmError(POINT_OUT_OF_BOUNDS)`) · `from_screen(p: Point) -> tuple[float, float]` · `child(crop_in_image: Rect, image_size: tuple[int, int]) -> ImageMapping` · `scale -> float` (image_w / crop_w).
- `fit_within(size: tuple[int, int], max_edge: int) -> tuple[int, int]` (en-boy korunur, asla büyütmez, min 1).
- `@dataclass MonitorInfo(index: int, device: str, rect: Rect, work_rect: Rect, dpi: int, scale: float, primary: bool)` · `list_monitors() -> list[MonitorInfo]` (birincil index 0, sonra sol→sağ) · `virtual_screen() -> Rect`.

- [ ] Testler:
```python
def test_fit_within(): assert fit_within((2560,1440),1600)==(1600,900) and fit_within((800,600),1600)==(800,600)
def test_mapping_identity(): m=ImageMapping(Rect(0,0,2560,1440),Rect(0,0,2560,1440),(2560,1440)); assert m.to_screen(100,200)==Point(100,200)
def test_mapping_scaled(): m=ImageMapping(Rect(0,0,2560,1440),Rect(0,0,2560,1440),(1600,900)); assert m.to_screen(800,450)==Point(1280,720)
def test_mapping_negative_origin(): m=ImageMapping(Rect(-1920,0,0,1080),Rect(0,0,1920,1080),(1600,900)); assert m.to_screen(0,0)==Point(-1920,0)
def test_norm1000(): m=ImageMapping(Rect(0,0,2560,1440),Rect(0,0,2560,1440),(1600,900)); assert m.to_screen(500,500,"norm1000")==Point(1280,720)
def test_child_zoom_chain(): ...  # 1600x900 önizlemede (400,225,400,225) zoom → 1600x900; child.to_screen(800,450) == Point(1280,720)
def test_out_of_bounds_raises(): ...  # x=1600 → EdmError POINT_OUT_OF_BOUNDS
```
- [ ] `test_mapping_roundtrip_scaled` (hypothesis): rastgele frame/crop/image boyutları (ölçek 0.25–4) için `to_screen(from_screen(p))` sonucu p'den en fazla `ceil(1/scale)` px sapar.
- [ ] `test_monitors_live_shape` (canlı değil): en az 1 monitör, tam olarak bir `primary`, `virtual_screen` tüm `rect`'leri kapsar.
- [ ] Commit: `feat(core): geometry, image mapping and monitor enumeration`

### T1.4 Pencereler, süreçler ve bütünlük düzeyi

**Files:** Create `src/edm/win32/windows.py`, `src/edm/win32/process.py`, `src/edm/perception/__init__.py`, `src/edm/perception/textnorm.py`, `tests/unit/test_windows_query.py`, `tests/unit/test_process.py`

**Interfaces:**
- `class Integrity(StrEnum)`: `untrusted, low, medium, high, system, unknown` · `integrity_rank(i) -> int` · `process_integrity(pid: int) -> Integrity` (`OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` → `OpenProcessToken(TOKEN_QUERY)` → `TokenIntegrityLevel`. Erişim reddi `unknown`) · `self_integrity() -> Integrity` · `process_exe(pid) -> str`.
- `@dataclass WindowInfo(hwnd: int, title: str, class_name: str, pid: int, exe: str, rect: Rect, minimized: bool, maximized: bool, visible: bool, cloaked: bool, topmost: bool, foreground: bool, monitor_index: int, integrity: Integrity, z_order: int)`. `rect` = `DWMWA_EXTENDED_FRAME_BOUNDS` (yoksa `GetWindowRect`).
- `@dataclass WindowQuery(kind: Literal["hwnd","pid","exe","class","title","regex","text"], value: str)` · `parse_window_query(q: str) -> WindowQuery` · `list_windows(include_minimized: bool = True, include_cloaked: bool = False) -> list[WindowInfo]` (yalnız görünür, sahipsiz veya ana pencereler, Z-sırası ile) · `select_window(cands: list[WindowInfo], q: WindowQuery) -> tuple[WindowInfo, list[WindowInfo]]` (eşleşme yoksa `EdmError(WINDOW_NOT_FOUND)`, çoksa en küçük `z_order` + alternatifler) · `resolve_window(q: str) -> tuple[WindowInfo, list[WindowInfo]]` · `window_info(hwnd: int) -> WindowInfo` · `root_window_at(p: Point) -> int` (`WindowFromPoint` → `GetAncestor(GA_ROOT)`).

- [ ] Testler: `test_parse_window_query` (`"hwnd:12"`→hwnd/12, `"exe:ACAD.EXE"`→exe/`acad.exe`, `"re:^Not.*"`→regex, `"autocad"`→text) · `test_select_prefers_topmost` (sahte 3 pencere, z 2/0/1 → z=0 seçilir, 2 alternatif) · `test_select_not_found` · `test_text_match_casefold_turkish` (`"İŞLEM"` sorgusu `"işlem penceresi"` başlığını bulur. Türkçe katlama `perception/textnorm.py::tr_fold` ile yapılır: önce `İ→i`, `I→ı`, sonra `casefold`. T1.4'te oluşturulur, T4.2'de yeniden kullanılır) · `test_self_integrity_known` (unknown değil) · `test_integrity_rank_order`.
- [ ] Commit: `feat(win32): window enumeration, queries and process integrity`

### T1.5 `doctor` ve `service.Edm` iskeleti

**Files:** Create `src/edm/service.py`, `src/edm/doctor.py`, `src/edm/fakes.py`, `tests/unit/test_doctor.py`; Modify `src/edm/cli.py`

**Interfaces:**
- `@dataclass Result(payload: dict[str, Any], image: bytes | None = None, mime: str | None = None)`
- `class Edm`: `__init__(self, cfg: Config | None = None, *, session_provider=get_session, capture_backends: dict | None = None, input_sink=None, clock=time.time)`. `build_default() -> Edm` (`EDM_FAKE=1` → `fakes` bileşenleri). `doctor() -> Result`.
- `run_doctor(edm) -> dict` anahtarları: `version, python, os_build, session{station,thread_desktop,input_desktop,state}, elevated, integrity, dpi_awareness, monitors[], virtual_screen, backends{gdi, wgc, printwindow, uia, ocr:{available, languages}}, killswitch{hotkey, failsafe_corner}, data_dir, hints[]`. `state != "ok"` ise `hints[0]` §10.3'teki `ISOLATED_DESKTOP` / `SECURE_DESKTOP` next_step metnini taşır.
- `fakes.py`: `FakeSession(state="ok")`, `FakeCaptureBackend` (deterministik 2560×1440 görüntü: koyu gri zemin + (200,200)-(300,300) kırmızı, (400,200)-(500,300) yeşil, (600,200)-(700,300) mavi kare), `FakeInputSink` (gönderilen olayları listeler, başlangıç `cursor_pos=Point(500, 500)` tutar — `(0,0)` failsafe köşesini yanlışlıkla tetiklememek için).
- CLI: `edm doctor` → JSON (stdout), çıkış 0.

- [ ] Testler: `test_doctor_keys(fake_edm)` · `test_doctor_isolated_hint` (`FakeSession(state="isolated_desktop")` → `hints[0]` "MCP" içerir) · `test_cli_doctor_json(monkeypatch)` (`EDM_FAKE=1`, JSON ayrıştırılabilir).
- [ ] Canlı (yerel): `uv run edm doctor` çıktısındaki `session.state` değerini PROGRESS'in "Ortam" bölümüne bir kez yaz (izole masaüstünde `isolated_desktop` beklenir, bu normaldir).
- [ ] Commit: `feat: doctor report, service facade and fake backends`

**Faz 1 kapısı:** Faz 0 komutları yeşil. `push`. PROGRESS güncellenir.

---

## Faz 2 — Yakalama motoru ve gözlemler

### T2.1 GDI arka ucu, boş kare tespiti, canlı test hedef uygulaması

**Files:** Create `src/edm/capture/__init__.py`, `src/edm/capture/base.py`, `src/edm/capture/gdi.py`, `tests/unit/test_blank.py`, `tests/live/conftest.py`, `tests/live/target_app.py`, `tests/live/test_capture_live.py`

**Interfaces:**
- `@dataclass Frame(image: Image.Image, screen_rect: Rect, backend: str, captured_at: float, attempts: list[dict[str, Any]])` (RGB).
- `class CaptureBackend(Protocol)`: `name: str` · `available() -> tuple[bool, str]` · `capture_rect(rect: Rect) -> Frame` · `capture_window(hwnd: int) -> Frame`.
- `is_blank(img: Image.Image) -> bool` (tasarım §7 eşikleri).
- `GdiBackend`: `mss` ile `capture_rect`. `capture_window` = `window_info(hwnd).rect` kırpması. Boyut uyuşmazlığı `EdmError(CAPTURE_FAILED)` üretir.
- `cursor_position() -> Point | None` (`GetCursorInfo`, gizliyse None).
- `tests/live/conftest.py`: `require_interactive` fiksürü `get_session().state != "ok"` ise `pytest.skip("LIVE-PENDING: <state>")` yapar. `target_app` fiksürü `target_app.py`'yi alt süreçte başlatır, `--log <tmp>` verir, pencereyi bekler (≤10 s), teardown'da sonlandırır (`kill`, ≤5 s).
- `target_app.py` (Tk, kendi DPI farkındalığı PMv2): başlık `EDM Target`, konum (100,100), istemci 800×600. İstemci (40,40)'ta 80×80 saf kırmızı, (160,40)'ta yeşil, (280,40)'ta mavi kare. `EDM-OK` düğmesi. Tek satırlık `Entry`. Etiket `Çalışma Ağı İğne Şüphe Öğün`. Tıklama, sürükleme ve tekerlek olaylarını ekran koordinatıyla JSONL olarak `--log` dosyasına yazan 300×200 tuval.

- [ ] Testler: `test_is_blank_uniform` (tek renk → True) · `test_is_blank_noise_false` (rastgele → False) · `test_is_blank_ui_like_false` (beyaz zemin + 10 px siyah şerit → False).
- [ ] Canlı L1 `test_gdi_pixel_colors` (`@pytest.mark.live`): hedef uygulamanın kırmızı karesinin merkez pikseli (±0) `(255,0,0)`, yeşil `(0,255,0)`, mavi `(0,0,255)`.
- [ ] Commit: `feat(capture): GDI backend, blank detection and live target app`

### T2.2 Pencere yakalama stratejisi: örtülme, WGC, PrintWindow, seçim

**Files:** Create `src/edm/capture/occlusion.py`, `src/edm/capture/wgc.py`, `src/edm/capture/printwindow.py`, `src/edm/capture/select.py`, `tests/unit/test_occlusion.py`, `tests/unit/test_select.py`

**Interfaces:**
- `visible_fraction(rect: Rect, owned: set[int], hit_test: Callable[[Point], int], grid: int = 7) -> float`
- `WgcBackend` (`windows-capture`, `uv add windows-capture`): tek kare alır ve `cfg.wgc_timeout_s` içinde gelmezse `EdmError(CAPTURE_FAILED, details={"backend":"wgc"})` üretir. Kütüphane hwnd hedeflemeyi desteklemiyorsa tam başlıkla hedefler; Windows 10 (build < 22000) üzerinde `draw_border=False` desteklenmiyorsa `draw_border=None` ile tekrar başlatır (karar DECISIONS'a yazılır). İçe aktarılamazsa `available()=(False, reason)`.
- `PrintWindowBackend`: `PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT=2)` + `GetDIBits`.
- `@dataclass CaptureTarget(kind: Literal["screen","monitor","window","region"], monitor: int | None = None, query: str | None = None, rect: Rect | None = None)` · `parse_target(s: str) -> CaptureTarget` (`"screen"`, `"monitor:1"`, `"window:exe:acad.exe"`, `"region:10,20,300,200"` = x,y,w,h. Geçersizse `INVALID_ARGUMENT`).
- `class Capturer(backends: dict[str, CaptureBackend], cfg: Config)`: `capture(target: CaptureTarget, restore: bool = False) -> tuple[Frame, WindowInfo | None]`. Sıra tasarım §7'deki tablodur. Görünürlük eşiği 0.98'dir. Simge durumunda: `restore=False` → `WINDOW_MINIMIZED`, `True` → `ShowWindow(SW_RESTORE)` + durulma bekleme. Boş karede sıradaki yedeğe geçilir. Her deneme `Frame.attempts`'a `{backend, ok, reason}` olarak eklenir. Hepsi boşsa `CAPTURE_BLANK`.

- [ ] Testler: `test_visible_fraction_full` (hit hep hedef → 1.0) · `test_visible_fraction_half` (sol yarı başka hwnd → ~0.43–0.57) · `test_parse_target_variants` · `test_capturer_screen_uses_gdi` · `test_capturer_falls_back_on_blank` (gdi boş, wgc hata, printwindow iyi → backend `printwindow`, attempts 3) · `test_capturer_all_blank_raises` · `test_capturer_minimized_requires_restore`.
- [ ] Canlı L2 `test_window_capture_size` (hedef pencere yakalama boyutu = DWM sınırları) · L3 `test_occluded_window_uses_wgc_or_printwindow` (hedefin üstüne ikinci bir Tk penceresi koy, sonuç `backend != "gdi"` ve kırmızı kare pikseli doğru).
- [ ] Commit: `feat(capture): window strategy with occlusion check, WGC and PrintWindow fallbacks`

### T2.3 Gözlem deposu ve görüntü işleme

**Files:** Create `src/edm/observe/__init__.py`, `src/edm/observe/store.py`, `src/edm/observe/render.py`, `tests/unit/test_store.py`, `tests/unit/test_render.py`

**Interfaces:**
- `@dataclass Mark(id: int, rect: Rect, label: str)` (ekran koordinatları).
- `@dataclass Observation(id: str, created_at: float, target: str, frame_rect: Rect, mapping: ImageMapping, original_path: Path, preview_path: Path, backend: str, window: dict[str, Any] | None, parent_id: str | None, marks: list[Mark], tags: list[str])` · `to_public() -> dict` (tasarım §10.1 `observation` nesnesi).
- `class ObservationStore(root: Path, cfg: Config, clock=time.time)`: `add(frame, preview: Image.Image, mapping, *, target, window=None, parent_id=None, marks=None, tags=()) -> Observation` (ID `o-YYYYMMDD-HHMMSS-NNNN`, süreçler arası benzersiz: zaman + 4 hane rastgele. Disk adı aynı) · `get(id) -> Observation` (yoksa `OBSERVATION_NOT_FOUND`) · `latest(tag: str | None = None) -> Observation | None` · `load_original(obs) -> Image.Image` · `prune(now: float | None = None) -> int`. İndeks `index.jsonl` dosyasına satır satır eklenir. Okuma bozuk satırı atlar.
- `render.py`: `make_preview(img, max_edge) -> Image.Image` · `draw_cursor(img, xy: tuple[float, float]) -> Image.Image` · `draw_grid(img, step: int = 100) -> Image.Image` · `draw_marks(img, marks_in_image: list[tuple[int, Rect]]) -> Image.Image` · `zoom_crop(original, crop: Rect, max_edge: int, factor: float | None) -> Image.Image` (factor None → uzun kenarı `max_edge`'e en fazla 4× büyüt) · `encode_image(img, max_bytes: int) -> tuple[bytes, str]`.

- [ ] Testler: `test_store_roundtrip_new_instance` (ekle → yeni `ObservationStore` örneği `get` ile aynı mapping'i okur) · `test_store_id_unique_1000` · `test_prune_by_age` (8 günlük kayıtlar silinir) · `test_prune_by_bytes` · `test_corrupt_index_line_skipped` · `test_grid_keeps_size` · `test_encode_respects_max_bytes` (4K gürültü görüntüsü → ≤1 500 000 bayt, mime jpeg) · `test_zoom_crop_factor_cap` (50×50 kırpma → en fazla 200×200).
- [ ] Commit: `feat(observe): observation store, previews, grid, zoom and encoding`

### T2.4 `screenshot`, `zoom`, `list_monitors`, `list_windows` servis yöntemleri + CLI

**Files:** Modify `src/edm/service.py`, `src/edm/cli.py`; Create `tests/unit/test_service_capture.py`

**Interfaces (Produces):** `Edm.screenshot(target="screen", max_edge=None, grid=False, cursor=True, marks=False, restore=False) -> Result` · `Edm.zoom(observation_id, x, y, w, h, coord_space="pixel", fresh=False, factor=None) -> Result` (`fresh=True` → kırpmanın ekran dikdörtgeni GDI ile yeniden yakalanır, yeni kök gözlem `parent_id` ile bağlanır) · `Edm.list_monitors() -> Result` · `Edm.list_windows(query=None, include_minimized=True) -> Result`. CLI: `edm shot --target … [--grid] [--max-edge N]`, `edm zoom --obs ID --x --y --w --h [--fresh]`, `edm monitors`, `edm windows [--query]`.

- [ ] Testler (sahte arka uç): `test_screenshot_payload` (`image_size==[1600,900]`, `scale==0.625`, görüntü baytları mevcut) · `test_zoom_maps_back` (zoom gözleminde kırmızı karenin merkezi `to_screen` ile (250,250)±1) · `test_zoom_fresh_links_parent` · `test_list_windows_fake`.
- [ ] Commit: `feat(service): screenshot, zoom, monitors and windows tools with CLI`

**Faz 2 kapısı:** Kapı komutları yeşil. Canlı L1–L3 ya PASS ya da `LIVE-PENDING` olarak PROGRESS'e yazılır. `push`.

---

## Faz 3 — Eylem motoru ve güvenlik

### T3.1 Düşük seviye girdi: olay üretimi

**Files:** Create `src/edm/actions/__init__.py`, `src/edm/actions/keys.py`, `src/edm/actions/mouse.py`, `src/edm/win32/input.py`, `tests/unit/test_keys.py`, `tests/unit/test_mouse_events.py`

**Interfaces:**
- `@dataclass(frozen=True) KeyEvent(vk: int, scan: int, flags: int)` · `MouseEvent(flags: int, dx: int = 0, dy: int = 0, data: int = 0)`
- `parse_chord(chord: str, vk_scan: Callable[[str], int] = default_vk_scan) -> list[int]` (ad tablosu: ctrl, alt, shift, win, enter, esc, tab, space, backspace, delete, insert, home, end, pageup, pagedown, up, down, left, right, f1–f24, printscreen, apps, capslock, volumeup, volumedown, volumemute, mediaplaypause. Tek karakter → `VkKeyScanW` ile taranır; dönüş `-1` (`0xFFFF`) ise `INVALID_ARGUMENT`, değilse düşük bayt `res & 0xFF`. Bilinmeyen ad → `INVALID_ARGUMENT`) · `chord_events(vks: list[int]) -> list[KeyEvent]` (bas sırayla, bırak ters sırayla, genişletilmiş tuşlara `KEYEVENTF_EXTENDEDKEY`) · `unicode_events(text: str) -> list[KeyEvent]` (`\n`→VK_RETURN, `\t`→VK_TAB, diğerleri UTF-16 birimleri `KEYEVENTF_UNICODE` aşağı+yukarı).
- `normalize_abs(p: Point, virtual: Rect) -> tuple[int, int]` (`round((x-left)*65535/(width-1))`) · `click_events(button: str, count: int) -> list[MouseEvent]` · `wheel_events(dy: int, dx: int) -> list[MouseEvent]` (çentik × 120).
- `class InputSink(Protocol)`: `send(events: Sequence[KeyEvent | MouseEvent]) -> int` · `move_to(p: Point) -> None` · `cursor_pos() -> Point`. `Win32InputSink`: `SendInput` kullanır. Dönüş < len ise `EdmError(INPUT_BLOCKED)`. `move_to` = `MOUSEEVENTF_MOVE|ABSOLUTE|VIRTUALDESK`, ardından `GetCursorPos` doğrulaması yapılır. Sapma ≥1 px ise `SetCursorPos` ile düzeltilir.

- [ ] Testler: `test_parse_chord_basic` (`"ctrl+shift+s"` → `[0x11, 0x10, 0x53]`) · `test_parse_chord_win_r` · `test_parse_chord_unknown` · `test_parse_chord_layout_letter` (sahte `vk_scan` `"ş"`→0xBA döndürünce `"ctrl+ş"` → `[0x11, 0xBA]`) · `test_chord_release_reverse` · `test_unicode_events_surrogates` (`"ğ😀"` → 6 olay: ğ için 2, 😀 için 2 birim × 2) · `test_unicode_newline_tab` · `test_normalize_abs_negative_virtual` (`Rect(-1920,0,2560,1440)`, `Point(-1920,0)` → `(0,0)`, `Point(2559,1439)` → `(65535,65535)`) · `test_wheel_events_sign`.
- [ ] Commit: `feat(input): key/mouse event generation and SendInput sink`

### T3.2 Guard: oturum, UIPI, kilit

**Files:** Create `src/edm/actions/guard.py`, `tests/unit/test_guard.py`

**Interfaces:** `class Guard(cfg, session_provider, killswitch, integrity_at: Callable[[Point], Integrity], self_integrity: Integrity)`: `preflight(point: Point | None) -> None`. Sıra tasarım §8 madde 1–3'tür (oturum → kill switch → UIPI). Bütünlük `unknown` ve kendimiz `medium` ise hedefin yüksek yetkili olduğu varsayılır ve `ELEVATION_REQUIRED` döner, mesaj "muhtemelen" içerir. `@contextmanager input_lock(timeout_s: float) -> Iterator[None]` (`CreateMutexW("Local\\EDM_INPUT_LOCK")` + `WaitForSingleObject`. Zaman aşımında `BUSY`. Terk edilmiş mutex `WAIT_ABANDONED` başarı sayılır).

- [ ] Testler: `test_preflight_ok` · `test_preflight_isolated` · `test_preflight_secure_desktop` · `test_preflight_elevation_required` (hedef high, self medium) · `test_preflight_unknown_integrity_assumed_elevated` · `test_preflight_aborted` (killswitch.triggered → `ABORTED_BY_USER`) · `test_input_lock_busy` (kilidi ayrı bir iş parçacığında tut, 0.2 s zaman aşımı → `BUSY`).
- [ ] Commit: `feat(guard): session, UIPI and inter-agent input lock preflight`

### T3.3 Acil durdurma (kill switch)

**Files:** Create `src/edm/actions/killswitch.py`, `tests/unit/test_killswitch.py`

**Interfaces:** `class KillSwitch(cfg, cursor_provider: Callable[[], Point], primary_origin: Point)`: `start_hotkey_thread() -> bool` (daemon iş parçacığı: `RegisterHotKey(None, 1, MOD_CONTROL|MOD_ALT|MOD_SHIFT|MOD_NOREPEAT, VK_F12)` + `GetMessageW` döngüsü. `WM_HOTKEY` gelince `signal()` çağrılır. Kayıt başarısızsa False döner, başka bir EDM süreci tutuyordur) · `signal() -> None` (`Local\EDM_ABORT` adlı manuel-reset olayını ayarlar, 2 s sonra sıfırlar) · `triggered() -> bool` (olay ayarlı **veya** `failsafe_corner` açıkken imleç `primary_origin` ±1 px içinde) · `stop() -> None`.

- [ ] Testler: `test_signal_sets_triggered` · `test_event_shared_across_instances` (iki örnek, biri `signal` → diğeri `triggered`) · `test_corner_failsafe` (sahte imleç (0,0) → True. (5,5) → False) · `test_corner_disabled_by_config`.
- [ ] Commit: `feat(safety): global kill switch hotkey and failsafe corner`

### T3.4 Fare/klavye servis yöntemleri, adresleme, stale koruması, durulma

**Files:** Create `src/edm/actions/addressing.py`, `src/edm/observe/diff.py`, `src/edm/actions/waits.py`, `tests/unit/test_addressing.py`, `tests/unit/test_service_actions.py`, `tests/unit/test_diff.py`; Modify `src/edm/service.py`, `src/edm/cli.py`

**Interfaces:**
- `@dataclass Address(observation_id: str | None = None, x: float | None = None, y: float | None = None, coord_space: CoordSpace = "pixel", mark: int | None = None, text: str | None = None, target: str = "screen", screen_x: int | None = None, screen_y: int | None = None)` · `validate_address(a: Address) -> Literal["obs","mark","text","screen"]` (tam olarak bir mod, yoksa `INVALID_ARGUMENT`) · `resolve_point(edm, a: Address) -> tuple[Point, Observation | None, list[str]]` (`text` modu T4.2'ye kadar `DEPENDENCY_MISSING` döndürür).
- `patch_diff(a: Image.Image, b: Image.Image) -> float` (ortalama mutlak fark / 255) · `diff_images(a, b, pixel_threshold: int = 24) -> DiffResult(changed_fraction: float, bbox: Rect | None)`.
- `check_stale(edm, obs: Observation, point: Point) -> None`: yaş > ttl → `STALE_OBSERVATION`. Pencere gözleminde `window_info(hwnd)` rect/başlık farkı veya `GetLastActivePopup` değişimi → `STALE_OBSERVATION`. `verify` açıkken 24×24 yama farkı > 0.15 → `STALE_OBSERVATION`.
- `wait_until(pred: Callable[[], bool], timeout_s: float, interval_s: float = 0.2) -> bool` · `wait_for_stable(grab: Callable[[], Image.Image], quiet_ms: int, timeout_ms: int) -> Image.Image` (ardışık iki kare farkı < 0.002 olduğunda sessiz sayılır).
- `Edm.click(addr: Address, button="left", count=1, modifiers: list[str] = [], verify=True, observe=True) -> Result` · `move_mouse(addr)` · `drag(from_addr, to_addr, button="left", duration_ms=300)` (20 ara nokta) · `scroll(addr, dy=0, dx=0)` · `type_text(text, interval_ms=0, observe=True)` · `press_keys(keys: str | list[str], repeat=1)`. Her eylemin sırası: `input_lock` → `guard.preflight` → `check_stale` → girdi → `wait_for_stable` → yeni gözlem (önceki hedefle aynı `target`; noktaya göre eylemlerde `screen`) → `logs/actions-*.jsonl` satırı.
- CLI: `edm click --obs ID --x --y [--norm1000] [--button] [--count]`, `edm click --screen X Y`, `edm move`, `edm drag`, `edm scroll --dy`, `edm type --text`, `edm keys ctrl+s`.

- [ ] Testler: `test_validate_address_exactly_one` · `test_click_maps_and_sends` (1600×900 önizlemede (156.25,156.25) → sahte imleç (250,250), olaylar sol aşağı+yukarı) · `test_click_norm1000` · `test_click_rejects_moved_window` (pencere gözleminden sonra sahte pencere rect değişti → `STALE_OBSERVATION`, sıfır olay) · `test_click_rejects_patch_change` (sahte arka uç kırmızı kareyi beyaza boyar → `STALE_OBSERVATION`) · `test_click_expired_observation` (saat +121 s) · `test_action_returns_new_observation` · `test_actions_logged_jsonl` · `test_patch_diff_identical_zero` · `test_diff_bbox`.
- [ ] Canlı L4 `test_click_accuracy` (hedef tuvaline 5 noktaya tıkla, log ±1 px) · L5 `test_click_norm1000_accuracy` · L6 `test_type_unicode` (`Entry`'ye `"ğüşıöçİĞÜŞÖÇ 123 €"`, UIA `ValuePattern` ile geri okuma birebir) · L7 `test_drag_and_scroll` · L9 `test_stale_after_move` (gözlem al, `window_action move`, eski gözlemle tıklama → STALE, log'da tıklama yok).
- [ ] Commit: `feat(actions): mouse/keyboard tools with addressing, stale guard and settle`

### T3.5 Pencere işlemleri, başlatma, bekleme koşulları, pano

**Files:** Create `src/edm/actions/windowops.py`, `src/edm/actions/launch.py`, `src/edm/actions/clipboard.py`, `tests/unit/test_launch.py`, `tests/unit/test_waits.py`, `tests/unit/test_clipboard.py`; Modify `src/edm/service.py`, `src/edm/cli.py`

**Interfaces:**
- `focus_window(hwnd: int) -> bool` (geri yükle → `SetForegroundWindow`. Reddedilirse `AttachThreadInput` + `BringWindowToTop` ile bir kez daha dener. En fazla 1 s doğrulama yapılır) · `window_action(hwnd, action: Literal["focus","minimize","maximize","restore","close","move","resize"], rect: Rect | None = None) -> None` (`close` = `WM_CLOSE`, zorla öldürme yok).
- `@dataclass LaunchSpec(kind: Literal["path","shortcut","aumid","url"], value: str)` · `resolve_launch_target(target: str, start_menu_dirs: list[Path], aumid_lookup: Callable[[str], str | None]) -> LaunchSpec` (var olan dosya yolu → path. `http(s)://` → url. Başlat menüsü `.lnk` dosyalarında `tr_fold` içerir-eşleşme, en kısa ad → shortcut. `Get-StartApps` çıktısında ad eşleşmesi → aumid. Hiçbiri yoksa `WINDOW_NOT_FOUND`, mesaj "uygulama bulunamadı") · `Edm.launch(target, args=[], wait_window=None, timeout_s=30) -> Result` (`ShellExecuteExW`. `shell:AppsFolder\<AUMID>`. `wait_window` regex'ine uyan **yeni** pencere görünür olup başlığı 1 s sabit kalana kadar bekler. Bu, açılış ekranlarını eler. Zaman aşımında `TIMEOUT`).
- `Edm.wait_for(kind: Literal["change","stable","window","window_gone","text"], target="screen", query=None, timeout_s=10) -> Result` (`timeout_s > 60` ise `INVALID_ARGUMENT`. `text` T4.2'den sonra etkinleşir. Öncesinde `DEPENDENCY_MISSING`).
- `clipboard.get_text() -> str | None`, `set_text(s: str) -> None`, `get_image() -> Image.Image | None` (`OpenClipboard` 10×50 ms deneme) · `Edm.clipboard(op, text=None) -> Result` · `Edm.window_action(window, action, rect=None) -> Result`.

- [ ] Testler: `test_resolve_launch_path(tmp_path)` · `test_resolve_launch_url` · `test_resolve_launch_shortcut_fold` (sahte dizinde `AutoCAD 2026 - Türkçe.lnk`, sorgu `autocad` → shortcut) · `test_resolve_launch_not_found` · `test_wait_until_timeout_fast` (0.3 s'de False) · `test_wait_for_rejects_over_60` · `test_clipboard_roundtrip_restores` (önceki pano metnini kaydet → `set_text("EDM-TEST-ğ")` → `get_text` eşit → eskiyi geri yükle; `finally` içinde).
- [ ] Commit: `feat(actions): window ops, app launch, wait conditions and clipboard`

### T3.6 Sıralı eylemler (`run_sequence`)

**Files:** Create `src/edm/actions/sequence.py`, `tests/unit/test_sequence.py`; Modify `src/edm/service.py`

**Interfaces:** `ALLOWED_STEP_TOOLS = frozenset({"click","move_mouse","drag","scroll","type_text","press_keys","wait_for"})` · `@dataclass Step(tool: str, args: dict[str, Any])` · `Edm.run_sequence(steps: list[Step], stop_on_error=True) -> Result`. Önce **tüm adımlar** doğrulanır: en fazla 25 adım, izinli araçlar, adres geçerliliği. Bir hata varsa hiçbir adım çalışmaz. Adımlar arasında ara gözlem alınmaz (`observe=False`). Yalnız sonunda bir gözlem alınır. Her adımdan önce `killswitch.triggered()` denetlenir. Pencere gözlemine bağlı adımlarda stale kontrolü her adımda yinelenir. Girdi kilidi tüm dizi boyunca tutulur. Sonuç `{"steps":[{index, tool, ok, error?}], "completed": n}` biçimindedir.

- [ ] Testler: `test_sequence_validates_all_first` (3. adım geçersiz → 0 olay) · `test_sequence_max_25` · `test_sequence_stops_on_error` · `test_sequence_continue_when_flag_false` · `test_sequence_aborts_on_killswitch_midway` (2. adımdan sonra tetikle → `completed==2`, son hata `ABORTED_BY_USER`).
- [ ] Canlı L10 `test_killswitch_mid_sequence` (`Local\EDM_ABORT` adlı olayı testten ayarla).
- [ ] Commit: `feat(actions): validated multi-step run_sequence`

**Faz 3 kapısı:** Kapı komutları yeşil. Canlı L4–L7, L9, L10 PASS veya LIVE-PENDING. `push`.

---

## Faz 4 — Algı: UIA, OCR, kullanıcı alıntısı

### T4.1 UIA öğeleri ve numaralı işaretler

**Files:** Create `src/edm/perception/__init__.py`, `src/edm/perception/uia.py`, `tests/unit/test_uia.py`; Modify `src/edm/service.py`

**Interfaces:** `@dataclass Element(mark: int, name: str, control_type: str, rect: Rect, enabled: bool, automation_id: str, value: str | None)` · `INTERACTIVE_TYPES = {"Button","CheckBox","ComboBox","Edit","Hyperlink","ListItem","MenuItem","RadioButton","TabItem","TreeItem","SplitButton","MenuBar","Slider","Spinner","DataItem","Document"}` · `collect_elements(hwnd: int, max_elements: int, timeout_s: float, provider: ElementProvider | None = None) -> tuple[list[Element], bool]`. Gezinme `uiautomation` ile ayrı bir iş parçacığında yapılır. Zaman aşımında o ana kadar toplananlar ve `truncated=True` döner. Ekran dışındaki, sıfır boyutlu ve görünmeyen öğeler elenir. Sıralama yukarıdan aşağı, soldan sağadır. `mark` 1'den başlar. `Edm.ui_elements(window=None, max_elements=150) -> Result` (pencere gözlemi + `draw_marks` önizleme. İşaretler gözleme kaydedilir) · `Address(mark=…)` çözümü = işaret dikdörtgeninin merkezi.

- [ ] Testler: `test_filter_and_order` (sahte ağaç: görünmez/sıfır boyutlu elenir, sıra doğru) · `test_collect_elements_timeout_partial` (sahte sağlayıcı her öğede 0.1 s uyur, timeout 0.35 s → `truncated=True`, 2–4 öğe) · `test_click_by_mark_resolves_center` · `test_uia_unavailable_maps_error` (sağlayıcı COM hatası → `UIA_UNAVAILABLE`).
- [ ] Canlı L2b: hedef uygulamada `EDM-OK` düğmesi `Button` olarak bulunur, `click(mark)` sonrası log'da düğme olayı görülür.
- [ ] Commit: `feat(perception): UIA element collection with set-of-mark overlay`

### T4.2 Windows OCR ile metin bulma

**Files:** Create `src/edm/perception/ocr.py`, `src/edm/perception/textnorm.py` (T1.4'te oluşturulduysa genişletilir), `tests/unit/test_ocr_match.py`; Modify `src/edm/service.py`, `src/edm/actions/addressing.py`

**Interfaces:** `uv add winrt-runtime winrt-Windows.Media.Ocr winrt-Windows.Graphics.Imaging winrt-Windows.Storage.Streams winrt-Windows.Globalization winrt-Windows.Foundation winrt-Windows.Foundation.Collections` (kurulamazsa ADR + `DEPENDENCY_MISSING` yolu) · `@dataclass OcrWord(text: str, rect: Rect)` / `OcrLine(text: str, words: list[OcrWord], rect: Rect)` (rect'ler girdi görüntüsü koordinatlarındadır) · `ocr_image(img: Image.Image, lang: str | None = None) -> list[OcrLine]` (kısa kenar < 800 ise 2× büyütüp sonuçları geri ölçekler. Dil: `tr-TR` varsa o, yoksa kullanıcı profili. Hiçbiri yoksa `DEPENDENCY_MISSING`, mesaj Windows dil paketi kurulumunu anlatır) · `tr_fold(s: str) -> str` · `match_text(lines, query, match: Literal["contains","exact","regex"]) -> list[TextMatch]` (`TextMatch(text: str, rect_image: Rect)`. Çok kelimeli sorgularda ardışık kelime dizisi birleşik dikdörtgen verir) · `Edm.find_text(query, target="screen", match="contains") -> Result` (eşleşmeler ekran + gözlem koordinatlarıyla) · `Address(text=…)` = ilk eşleşmenin merkezi. Birden fazla eşleşme varsa `warnings` eklenir.

- [ ] Testler: `test_tr_fold` (`tr_fold("ŞÜPHE İĞNE IŞIK") == "şüphe iğne ışık"`) · `test_match_contains_turkish` · `test_match_multiword_union_rect` · `test_match_regex` · `test_ocr_upscale_maps_back` (sahte motor 2× görüntüde (100,100,200,140) döndürür → (50,50,100,70)).
- [ ] Canlı L8 `test_find_text_turkish` (`Şüphe` kutusu hedef etiketin dikdörtgeniyle örtüşür).
- [ ] Commit: `feat(perception): offline Windows OCR text search with Turkish folding`

### T4.3 Kullanıcı alıntısı (`edm snip`)

**Files:** Create `src/edm/snip/__init__.py`, `src/edm/snip/overlay.py`, `tests/unit/test_snip.py`; Modify `src/edm/service.py`, `src/edm/cli.py`

**Interfaces:** `normalize_drag(p1: Point, p2: Point, min_size: int = 4) -> Rect | None` · `run_snip(frozen: Image.Image, virtual: Rect, prompt: str | None, timeout_s: float) -> Rect | None`. Önce ekran yakalanır. Sonra her monitör için kenarlıksız, en üstte, tam ekran bir Tk penceresi bu donmuş görüntüyü 1:1 gösterir ve üstüne yarı saydam karartma çizer. Sürükleme dikdörtgeni çizer. Bırakınca onaylanır, `Esc` iptal eder. Zaman aşımında None döner. Süreç DPI farkındalığı Tk'den önce ayarlanır. Sonuç donmuş görüntüden kırpılan bir gözlemdir (`tags=["user_snip"]`). `Edm.request_user_region(prompt=None, timeout_s=120) -> Result` (iptal/zaman aşımı: `ok:true, details.cancelled:true`) · `Edm.get_user_snips(limit=1) -> Result` · CLI `edm snip [--prompt]`. Belgede kullanıcının Windows kısayol tuşu ataması anlatılır (`.lnk` → "Kısayol tuşu").

- [ ] Testler: `test_normalize_drag_any_direction` ((300,200)→(100,50) = `Rect(100,50,300,200)`) · `test_normalize_drag_too_small` · `test_get_user_snips_latest_first`.
- [ ] Canlı L11 `test_snip_driven_by_edm` (`edm snip` alt süreçte başlar, EDM kendi `drag`'ı ile (500,300)→(900,600) çizer, sonuç gözlemin `frame_rect`'i ±2 px).
- [ ] Commit: `feat(snip): user-drawn region capture overlay`

**Faz 4 kapısı:** Kapı komutları yeşil. Canlı L2b, L8, L11 PASS veya LIVE-PENDING. `push`.

---

## Faz 5 — Arayüzler: CLI, MCP, entegrasyonlar

### T5.1 CLI tamamlama

**Files:** Modify `src/edm/cli.py`; Create `tests/unit/test_cli.py`

**Interfaces:** Tasarım §10.4'teki tüm alt komutlar `argparse` alt ayrıştırıcılarıyla tanımlanır. Her biri `Edm` yöntemine birebir eşlenir. Çıktı `json.dumps(payload, ensure_ascii=False)` ile yazılır. Görüntü baytları stdout'a yazılmaz, `observation.path` yeterlidir. `EdmError` → stderr'e payload + çıkış 2. Beklenmeyen hata → `INTERNAL` payload + çıkış 1. 90 s bekçi (`threading.Timer` → `os._exit(124)`). `edm prune`.

- [ ] Testler: `test_every_subcommand_parses` (tablo: argv → çağrılan yöntem adı + argümanlar, sahte `Edm`) · `test_exit_code_on_edm_error` · `test_json_utf8_output` (`ğ` kaçırılmadan basılır).
- [ ] Commit: `feat(cli): complete command surface with JSON output and exit codes`

### T5.2 MCP stdio sunucusu

**Files:** Create `src/edm/mcp_server.py`, `tests/integration/test_mcp_stdio.py`; Modify `src/edm/cli.py` (`edm mcp`)

**Interfaces:** `build_server(edm: Edm | None = None) -> FastMCP` (ad `edm`. Araçlar tasarım §10.2'deki 20 adla, düz parametrelerle. Açıklamalar İngilizcedir ve her biri strateji ipucu içerir. Örneğin `screenshot`: "Prefer ui_elements/find_text for clicking. Use zoom for small targets."). Her araç `list[TextContent | ImageContent]` döndürür: ilk eleman payload JSON'udur, görüntü varsa ikinci eleman `ImageContent`'tir. `EdmError` istisna olarak fırlatılmaz, `ok:false` payload'u olarak döner (SDK destekliyorsa `isError=True`). `run_stdio() -> None` sunucu başlamadan önce `ensure_dpi_awareness()` ve `killswitch.start_hotkey_thread()` çağırır. Kurulu `mcp` sürümünün API'si `uv run python -c "import mcp; print(mcp.__version__)"` ve paket kaynağından doğrulanır. Plandaki adlar farklıysa SDK'ya uyulur ve ADR yazılır.

- [ ] Testler (`EDM_FAKE=1`, SDK'nın stdio istemcisiyle alt süreç `uv run edm mcp`, testte 30 s zaman aşımı): `test_tools_listed_exact_names` (20 adın kümesi birebir) · `test_doctor_call` · `test_screenshot_returns_image_content` (mime `image/png` veya `image/jpeg`, base64 çözülür, boyut 1600×900) · `test_error_payload_not_exception` (`zoom` geçersiz id → `ok:false`, `OBSERVATION_NOT_FOUND`).
- [ ] Commit: `feat(mcp): stdio MCP server exposing all EDM tools`

### T5.3 Kullanıcı başlatmalı loopback HTTP modu

**Files:** Create `src/edm/http_server.py`, `tests/integration/test_http_mode.py`; Modify `src/edm/cli.py` (`edm serve-http`)

**Interfaces:** `run_http(host: str = "127.0.0.1", port: int = 8765, token_path: Path | None = None) -> None`. Yalnızca `127.0.0.1` veya `::1` kabul edilir, başka host `INVALID_ARGUMENT` ile reddedilir. Belirteç `%APPDATA%\EDM\http-token` dosyasındadır (yoksa `secrets.token_urlsafe(32)` ile üretilir, ilk çalıştırmada bir kez basılır). `Authorization: Bearer` zorunludur. Tarayıcı `Origin` başlığı varsa ve loopback değilse 403 döner. MCP Streamable HTTP SDK'nın ASGI uygulamasıyla sunulur. **Bu modu yalnız kullanıcı kendi oturumunda başlatır. Uygulayıcı ajan bunu izole masaüstünü aşmak için başlatmaz ve yapılandırmaz.**

- [ ] Testler: `test_rejects_non_loopback_host` · `test_401_without_token` · `test_403_foreign_origin` · `test_tools_list_with_token` (ASGI test istemcisi, `EDM_FAKE=1`).
- [ ] Commit: `feat(mcp): user-started loopback streamable HTTP mode with token auth`

### T5.4 İstemci entegrasyonları, kurulum betiği ve ajan becerisi

**Files:** Create `docs/integrations/antigravity.md`, `docs/integrations/codex.md`, `docs/integrations/claude-code.md`, `docs/integrations/gemini-cli.md`, `integrations/skills/edm-desktop/SKILL.md`, `scripts/install.ps1`, `tests/unit/test_skill_file.py`

**İçerik kararları:**
- Kurulum yöntemi: `uv tool install --editable C:\Users\hsyn\Desktop\EDM`. Komut: `edm mcp`.
- Antigravity: `~/.gemini/config/mcp_config.json` → `{"mcpServers":{"edm":{"command":"edm","args":["mcp"]}}}`. **İlk doğrulama:** Kayıttan sonra ajana `doctor` çağrısı yaptırılır. `session.state=="ok"` ise stdio yeterlidir. `isolated_desktop` ise kullanıcı `edm serve-http`'yi kendi PowerShell'inde başlatır ve `{"url":"http://127.0.0.1:8765/mcp"}` girdisini kullanır. Belirteç başlığının istemcide nasıl verileceği güncel Antigravity belgesinden doğrulanır. Desteklenmiyorsa bu sınır belgeye açıkça yazılır.
- Codex: `~/.codex/config.toml` → `[mcp_servers.edm]`, `command = "edm"`, `args = ["mcp"]`. Claude Code: `claude mcp add --scope user edm -- edm mcp`. Gemini CLI: `~/.gemini/settings.json` → `mcpServers.edm`. Her belgede yapılandırma anahtarları güncel resmî belgeden doğrulanır. Doğrulanamayan satır "doğrulanacak" diye işaretlenir.
- `scripts/install.ps1`: `uv` kontrolü → `uv tool install --editable` → `edm doctor` → her istemci için yapıştırılacak parçaları basar. `-WriteConfig` verilmedikçe hiçbir istemci yapılandırmasına dokunmaz. Verilirse önce `<dosya>.bak-<zaman>` yedeği alır, JSON/TOML'ı ayrıştırıp yalnız `edm` girdisini ekler.
- `SKILL.md`: frontmatter `name: edm-desktop`, `description` (ne zaman: masaüstü programı görme/kontrol). Gövde: tasarım §11 strateji merdiveni, döngü freni, hata kodu → davranış tablosu, uygulama notlarına bağlantı. 150 satırı geçmez.

- [ ] Testler: `test_skill_frontmatter` (name ve description var, gövde ≤150 satır) · `test_install_script_has_no_default_writes` (betikte `-WriteConfig` koşulu dışında `Set-Content`/`Out-File` yok; basit metin taraması).
- [ ] Commit: `docs(integrations): client setup guides, installer and agent skill`

**Faz 5 kapısı:** Kapı komutları yeşil. `uv tool install --editable .` başarılı. `edm doctor` çalışıyor. `push`.

---

## Faz 6 — Kabul, belgeler, sürüm ve DUR

### T6.1 Canlı kabul paketi ve gerçek uygulama matrisi

**Files:** Create `scripts/run-live-acceptance.ps1`, `docs/acceptance/TEMPLATE.md`, `docs/app-notes/autocad.md`, `docs/app-notes/winrar.md`, `docs/app-notes/chrome.md`, `docs/app-notes/g-menu.md`

- [ ] `run-live-acceptance.ps1`: `edm doctor` → `state != ok` ise açık mesajla çıkar (kod 3). Sonra `uv run pytest -m live --timeout=120 -p no:cacheprovider` → sonuçları `docs/acceptance/live-YYYY-MM-DD.md` dosyasına şablonla yazar (ekran görüntüsü **eklemez**, yalnız metin).
- [ ] Uygulayıcının ortamı izoleyse betiği **çalıştırmayı denemeye devam etmez**. PROGRESS'e `LIVE-PENDING` yazar ve kullanıcıya verilecek komutu FINAL-REPORT'a koyar.
- [ ] Uygulama notları ([02-TEST-VE-KABUL.md](02-TEST-VE-KABUL.md) M1–M7) "önerilen yöntem / bilinen tuzak / doğrulama durumu" başlıklarıyla yazılır. Doğrulanmamış iddialar "doğrulanacak" diye işaretlenir.
- [ ] Commit: `test(acceptance): live acceptance runner, template and app notes`

### T6.2 README'ler, değişiklik günlüğü, güvenlik notu

**Files:** Modify `README.md`, `README.tr.md`; Create `CHANGELOG.md`, `SECURITY.md`

- [ ] README: ne yapar, kurulum (3 komut), istemci bağlantıları, araç tablosu, güvenlik/gizlilik uyarısı (ekranda görünen her şey AI istemcisine gidebilir), bilinen sınırlar, lisans. Türkçe sürüm eşdeğerdir.
- [ ] Commit: `docs: README (EN/TR), changelog and security notes`

### T6.3 Sürüm etiketi, final rapor, DUR

**Files:** Modify `pyproject.toml` (sürüm), `src/edm/__init__.py`; Create `docs/plan/FINAL-REPORT.md`

- [ ] Kapı komutları + CI yeşil.
- [ ] Canlı L1–L11 kullanıcı masaüstünde PASS ise sürüm `0.1.0` olur, etiket `v0.1.0` atılır. Değilse sürüm `0.1.0rc1`, etiket `v0.1.0-rc1` olur.
- [ ] `FINAL-REPORT.md`: tamamlanan görevler, BLOCKED/LIVE-PENDING listesi, kullanıcının çalıştıracağı tek komut (`powershell -ExecutionPolicy Bypass -File scripts\run-live-acceptance.ps1`), bilinen sınırlar, IDEAS özeti.
- [ ] `git push origin main --tags`.
- [ ] **DUR.** IDEAS.md'deki hiçbir maddeye başlanmaz. Kullanıcıya rapor bağlantısı verilir.
