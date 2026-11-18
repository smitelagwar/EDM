# EDM v0.1 İlerleme Takibi (PROGRESS)

> Güncelleme kuralı: Her görev bittiğinde kutuyu işaretle, kısa commit hash'ini ve tek cümlelik notu ekle. Yüzde hesabı işaretli `[x]` görev sayısına göre (`round(tamamlanan * 100 / 27)`) yapılır.
> Durum işaretleri: `[ ]` bekliyor · `[x]` tamamlandı · `[!]` `BLOCKED` ([BLOCKERS.md](BLOCKERS.md)) · `[~]` `LIVE-PENDING` (izole masaüstü)

## İlerleme Özeti
- **Genel İlerleme:** `%89 (24 / 27 görev)`
- **Aktif Faz:** `Faz 6 — Kabul, belgeler, sürüm ve DUR`
- **Faz Yüzdeleri:** Faz 0 `%100 (2/2)` · Faz 1 `%100 (5/5)` · Faz 2 `%100 (4/4)` · Faz 3 `%100 (6/6)` · Faz 4 `%100 (3/3)` · Faz 5 `%100 (4/4)` · Faz 6 `%0 (0/3)`

## Ortam (İlk oturumda 1 kez doldurulur)
- **OS / Build:** `Windows 10 Pro 22H2 (Build 19045)`
- **Ekran / GPU:** `2560x1440 primary, NVIDIA GeForce RTX 4060 + AMD Radeon(TM) Graphics`
- **Python / uv:** `Python 3.12.14 / uv 0.12.5`
- **`edm doctor` → `session.state`:** `isolated_desktop (WinSta0\exebox-...)`

---

## Faz 0 — İskelet ve araç zinciri
- [x] **T0.1** Proje iskeleti, CI ve `edm --version` — ac3af95 — 2 test yeşil; paket iskeleti, Ruff/mypy/pytest ayarları ve CI akışı eklendi.
- [x] **T0.2** Hata modeli ve yapılandırma — 295674b — 15 test yeşil; 20 ErrorCode, EdmError payload ve TOML Config yükleyici eklendi.
- [x] **Faz 0 Kapısı:** `ruff` + `mypy` + `pytest` + CI yeşil → `git push origin main`

## Faz 1 — Win32 temel katman ve `doctor`
- [x] **T1.1** ctypes bağları ve Per-Monitor-V2 DPI farkındalığı — e15d29f — 2 test yeşil; 6 Win32 DLL prototipi ve idempotent PMv2 DPI farkındalığı eklendi.
- [x] **T1.2** Oturum / masaüstü sınıflandırma (`WinSta0\Default` vs `exebox` vs `Winlogon`) — b2f80e5 — 14 test yeşil; WinSta/Desktop/WTS oturum sınıflandırıcı eklendi.
- [x] **T1.3** Geometri, `ImageMapping` (`pixel` / `norm1000` / zincirleme `zoom`) ve monitörler — 54a240f — 10 test yeşil; Rect/ImageMapping (hypothesis doğrulamalı) ve monitör listesi eklendi.
- [x] **T1.4** Pencereler, süreç bütünlük düzeyi (`Integrity`) ve `tr_fold` — fab08e9 — 13 test yeşil; pencere sorgulama, Z-sırası seçimi, süreç bütünlüğü ve Türkçe katlama eklendi.
- [x] **T1.5** `doctor`, `service.Edm` iskeleti ve `fakes.py` — 7d30429 — 3 test yeşil; `run_doctor`, `Edm` facade, sahte arka uçlar ve `edm doctor` CLI eklendi.
- [x] **Faz 1 Kapısı:** Kapı komutları yeşil + `Ortam` tablosu güncellendi → `git push origin main`

## Faz 2 — Yakalama motoru ve gözlemler
- [x] **T2.1** GDI arka ucu (`mss`), boş kare tespiti ve `tests/live/target_app.py` — c970843 — 3 birim + 1 canlı (skip) test; GdiBackend, is_blank ve target_app eklendi.
- [x] **T2.2** Örtülme hesabı, WGC (`windows-capture`), `PrintWindow` ve arka uç seçici (`Capturer`) — 6e065b7 / 631424a — 9 birim + 2 canlı (skip) test; WGC Win10 border yedeği ve PrintWindow DWM kırpması doğrulandı.
- [x] **T2.3** Gözlem deposu (`ObservationStore`), önizleme küçültme/JPEG basamakları, ızgara, zoom — 236d5e0 — 14 test yeşil; ObservationStore, JPEG/PNG basamaklı kodlama ve zoom eklendi.
- [x] **T2.4** `screenshot`, `zoom`, `list_monitors`, `list_windows` servis yöntemleri ve CLI — f8f30c3 / 88f83dc — 8 test yeşil; service facade, CLI alt komutları ve fake sağlayıcılar eklendi.
- [~] **L1** `test_gdi_pixel_colors` — `LIVE-PENDING: isolated_desktop`
- [~] **L2** `test_window_capture_size` — `LIVE-PENDING: isolated_desktop`
- [~] **L3** `test_occluded_window_uses_wgc_or_printwindow` — `LIVE-PENDING: isolated_desktop`
- [x] **Faz 2 Kapısı:** Kapı komutları yeşil; L1–L3 PASS veya `LIVE-PENDING` → `git push origin main`

## Faz 3 — Eylem motoru ve güvenlik
- [x] **T3.1** Tuş/fare olay üretimi (`VkKeyScanW`, UTF-16 Unicode) ve `Win32InputSink` — f52aa34 — 12 test yeşil; klavye/fare olay üretici, Catmull-Rom yol ve SendInput sink eklendi.
- [x] **T3.2** `Guard` (oturum, UIPI tespiti, `Local\EDM_INPUT_LOCK` mutex) — ad888ae — 8 test yeşil; oturum/killswitch/UIPI preflight ve mutex kilidi eklendi.
- [x] **T3.3** `KillSwitch` (`Ctrl+Alt+Shift+F12` + `Local\EDM_ABORT` + `(0,0)` köşe kilidi) — 713fe72 — 5 test yeşil; global hotkey thread, ortak abort event ve köşe kilidi eklendi.
- [x] **T3.4** Adresleme, `diff`, `check_stale` (24×24 yama), `wait_for_stable`, fare/klavye araçları — ab461a2 — 14 birim + 6 canlı (skip) test; adresleme, stale/diff ve tüm fare/klavye servis araçları eklendi.
- [x] **T3.5** `window_action`, `launch` (`ShellExecuteExW` / Start Menu / AUMID), `wait_for`, `clipboard` — 2cee41b / cb66bd1 — 9 test yeşil (2 yeni guard/launch testi dahil); UIPI/preflight ve HGLOBAL temizliği doğrulandı.
- [x] **T3.6** Çok adımlı `run_sequence` (ön doğrulama, max 25 adım, her adımda killswitch + stale) — f5e54f4 — 5 test yeşil; reentrant kilit, abort kesmesi ve release_held eklendi.
- [~] **L4** `test_click_accuracy` — `LIVE-PENDING: isolated_desktop`
- [~] **L5** `test_click_norm1000_accuracy` — `LIVE-PENDING: isolated_desktop`
- [~] **L6** `test_type_unicode` — `LIVE-PENDING: isolated_desktop`
- [~] **L7** `test_drag_and_scroll` — `LIVE-PENDING: isolated_desktop`
- [~] **L9** `test_stale_after_move` — `LIVE-PENDING: isolated_desktop`
- [~] **L10** `test_killswitch_mid_sequence` — `LIVE-PENDING: isolated_desktop`
- [~] **L12** `test_draw_path_continuous` — `LIVE-PENDING: isolated_desktop`
- [x] **Faz 3 Kapısı:** Kapı komutları yeşil; L4–L7, L9, L10, L12 PASS veya `LIVE-PENDING` → `git push origin main`

## Faz 4 — Algı: UIA, OCR, kullanıcı alıntısı
- [x] **T4.1** UIA öğe toplama (5 s zaman aşımı) ve Set-of-Mark (`marks`) numaralandırma — f253dd7 / a9af267 — 5 test yeşil; thread zaman aşımı, GetPattern ve `ui_elements` entegre edildi.
- [x] **T4.2** Çevrimdışı Windows OCR (`winrt-*`) ve Türkçe katlamalı metin arama (`find_text`) — d737244 / a9af267 / 6acd85a — 8 test yeşil; `tr` OCR, 2× büyütme, `find_text` ve `Address(text=...)` eklendi.
- [x] **T4.3** Kullanıcı dikdörtgen alıntısı (`edm snip` + Tk donmuş ekran overlay) — f461fdb / a9af267 — 17 test yeşil; `run_snip` overlay, `request_user_region` ve `get_user_snips` eklendi.
- [~] **L2b** `test_uia_button_click` — `LIVE-PENDING: isolated_desktop`
- [~] **L8** `test_find_text_turkish` — `LIVE-PENDING: isolated_desktop`
- [~] **L11** `test_snip_driven_by_edm` — `LIVE-PENDING: isolated_desktop`
- [x] **Faz 4 Kapısı:** Kapı komutları yeşil; L2b, L8, L11 PASS veya `LIVE-PENDING` → `git push origin main`

## Faz 5 — Arayüzler: CLI, MCP, entegrasyonlar
- [x] **T5.1** Tam CLI (`edm <subcommand>`, JSON stdout, çıkış kodları 0/1/2, 90 s bekçi) — 21a1f7c — 28 test yeşil; tüm §10.4 alt komutları, çıkış kodları ve bekçi eklendi.
- [x] **T5.2** MCP `stdio` sunucusu (20 sabit araç + `ImageContent`) — 657c35c — 4 entegrasyon testi yeşil; §10.2'deki 23 araç ve base64 ImageContent eklendi.
- [x] **T5.3** Kullanıcı başlatmalı loopback HTTP modu (`127.0.0.1` / `::1`, Bearer token, Origin kontrolü) — a99acaa — 5 entegrasyon testi yeşil; loopback ASGI, Bearer token ve Origin koruması eklendi.
- [x] **T5.4** İstemci kılavuzları (Antigravity, Codex, Claude Code, Gemini CLI), `scripts/install.ps1` ve `SKILL.md` — be5c004 — 2 test yeşil; 4 istemci kılavuzu, install.ps1 ve SKILL.md eklendi.
- [x] **Faz 5 Kapısı:** Kapı komutları + `uv tool install --editable .` + `edm doctor` yeşil → `git push origin main`

## Faz 6 — Kabul, belgeler, sürüm ve DUR
- [ ] **T6.1** `scripts/run-live-acceptance.ps1`, kabul şablonu ve uygulama notları (`autocad`, `winrar`, `chrome`, `g-menu`)
- [ ] **T6.2** `README.md` (EN), `README.tr.md` (TR), `CHANGELOG.md`, `SECURITY.md` güncellemesi
- [ ] **T6.3** Sürüm etiketi (`v0.1.0` veya `v0.1.0-rc1`), `FINAL-REPORT.md`, `git push origin main --tags` → **DUR**

## Gerçek Uygulama Doğrulama Matrisi (Kullanıcı Oturumunda)
- [ ] **M1** AutoCAD (DirectX tuval + zoom ile küçük ikon)
- [ ] **M2** WinRAR (UIA diyalog + CLI önceliği)
- [ ] **M3** Chrome (OS dosya diyaloğu + DOM ayrımı)
- [ ] **M4** AOC G-Menu (UIPI tespiti + yönetici EDM ile kontrol)
- [ ] **M5** UAC / Kilit ekranı tespiti
- [ ] **M6** %125 / %150 DPI ölçekleme doğruluğu
- [ ] **M7** Türkçe klavye + pano geri yükleme
- [ ] **M8** İnsan gibi sürekli çizim / basılı tutma (Paint / AutoCAD)

## Günlük / Deneme Notları
*(3 deneme kuralı kapsamındaki hipotezler ve faz özetleri buraya işlenir.)*
