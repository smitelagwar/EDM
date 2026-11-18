# EDM v0.1 Canlı Kabul Raporu Şablonu

> **Not:** Bu şablon `scripts/run-live-acceptance.ps1` ve manuel uygulama doğrulaması için kullanılır. Gizlilik kuralı (`ADR-007`) gereği ekran görüntüleri depoya eklenmez; yalnız metin sonuçları kaydedilir.

- **Tarih:** `YYYY-MM-DD`
- **Oturum (`edm doctor`):** `WinSta0\Default` (`state: ok`)
- **Windows / Python:** `10.0.19045` / `3.12.x`
- **DPI / Monitör:** `per_monitor_v2` / `2560x1440`

## 1. Otomatik Canlı Kabul Testleri (L1–L12)

| ID | Test Adı | Durum (`PASS` / `FAIL` / `LIVE-PENDING`) | Not |
|---|---|---|---|
| **L1** | `test_gdi_pixel_colors` | `LIVE-PENDING` | Kırmızı/yeşil/mavi kare merkez pikselleri |
| **L2** | `test_window_capture_size` | `LIVE-PENDING` | `DWMWA_EXTENDED_FRAME_BOUNDS` boyut eşleşmesi |
| **L2b** | `test_uia_button_click` | `LIVE-PENDING` | `ui_elements` + `click(mark)` (`EDM-OK`) |
| **L3** | `test_occluded_window_uses_wgc_or_printwindow` | `LIVE-PENDING` | Örtülü pencerede WGC/PrintWindow yedeği |
| **L4** | `test_click_accuracy` | `LIVE-PENDING` | Önizleme (`pixel`) tıklama isabeti (±1 px) |
| **L5** | `test_click_norm1000_accuracy` | `LIVE-PENDING` | `norm1000` tıklama isabeti (±1 px) |
| **L6** | `test_type_unicode` | `LIVE-PENDING` | Türkçe ve Unicode metin yazımı |
| **L7** | `test_drag_and_scroll` | `LIVE-PENDING` | Sürükleme (20 ara nokta) ve tekerlek |
| **L8** | `test_find_text_turkish` | `LIVE-PENDING` | Çevrimdışı Windows OCR (`Şüphe`) |
| **L9** | `test_stale_after_move` | `LIVE-PENDING` | Pencere taşındığında `STALE_OBSERVATION` |
| **L10** | `test_killswitch_mid_sequence` | `LIVE-PENDING` | `Local\EDM_ABORT` ile dizi ortası kesme |
| **L11** | `test_snip_driven_by_edm` | `LIVE-PENDING` | `edm snip` overlay sürükleme (±2 px) |
| **L12** | `test_draw_path_continuous` | `LIVE-PENDING` | `draw_path` tek `down` + `Motion` + tek `up` |

## 2. Gerçek Uygulama Doğrulama Matrisi (M1–M8)

| ID | Senaryo | Durum | Gözlem Özeti |
|---|---|---|---|
| **M1** | AutoCAD (komut satırı, ribbon `zoom` + `click`, DirectX tuval) | `doğrulanacak` | |
| **M2** | WinRAR (`rar.exe` CLI + GUI `ui_elements` `mark`) | `doğrulanacak` | |
| **M3** | Chrome (DOM araçları + yerel dosya diyaloğu OCR/UIA) | `doğrulanacak` | |
| **M4** | AOC G-Menu (UIPI `ELEVATION_REQUIRED` tespiti) | `doğrulanacak` | |
| **M5** | UAC / Kilit Ekranı (`SECURE_DESKTOP` / `SESSION_LOCKED`) | `doğrulanacak` | |
| **M6** | Ölçekli Ekran (%125 / %150 DPI `to_screen` ±1 px) | `doğrulanacak` | |
| **M7** | Türkçe Klavye (`VkKeyScanW`) + Pano Geri Yükleme | `doğrulanacak` | |
| **M8** | İnsan Gibi Sürekli Çizim (`draw_path`, `mouse_button`, `key_state`) | `doğrulanacak` | |
