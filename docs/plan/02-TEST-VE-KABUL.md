# EDM v0.1 Test ve Kabul Stratejisi

> Bağlı tasarım: [00-TASARIM.md](00-TASARIM.md) · Uygulama planı: [01-UYGULAMA-PLANI.md](01-UYGULAMA-PLANI.md) · Çalışma kuralları: [../../AGENTS.md](../../AGENTS.md)

## 1. Kalite kapıları (her faz sonunda zorunlu)

Her görev ve faz sonunda çalıştırılacak standart kapı komutları:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
$env:EDM_FAKE="1"; uv run pytest
```

Kurallar:
- `pytest` varsayılan olarak `-m "not live" --timeout=60` ile koşar; ağ veya gerçek kullanıcı masaüstü gerektirmez.
- Hiçbir kapı script'i hata varken `0` çıkış kodu döndüremez.
- Birim ve entegrasyon testleri `EDM_FAKE=1` veya sahte protokol nesneleriyle deterministik çalışır.

## 2. Test katmanları

| Katman | Konum | Koşul | Amaç |
|---|---|---|---|
| **Birim** | `tests/unit/` | Her ortam (CI + izole masaüstü) | Geometri, DPI eşlemesi, sorgu ayrıştırma, hata modeli, stale yama farkı, Türkçe katlama, key/mouse olay üretimi, store budama |
| **Entegrasyon** | `tests/integration/` | `EDM_FAKE=1` (alt süreç ≤ 30 s) | MCP `stdio` araç listesi + base64 `ImageContent` dönüşü, loopback HTTP bearer/origin koruması, CLI çıkış kodları |
| **Canlı Kabul** | `tests/live/` | `@pytest.mark.live`, `session.state == "ok"` | Gerçek Windows DWM/GDI/WGC/PrintWindow, `SendInput`, UIA, Windows OCR, `edm snip` çizim overlay'i |

> **İzole masaüstü kuralı:** Komut ortamı `WinSta0\exebox-...` içindeyse `require_interactive` fiksürü canlı testleri `LIVE-PENDING: isolated_desktop` olarak atlar. Bu bir hata değildir; ajan masaüstü değiştirmeye çalışmaz, [PROGRESS.md](PROGRESS.md) dosyasına `LIVE-PENDING` işler.

## 3. Canlı kabul testleri (L1–L11)

Tüm canlı testler izole Tk hedef uygulaması (`tests/live/target_app.py`) veya alt süreç (`edm snip`) üzerinde koşar; kullanıcının açık iş pencerelerine dokunmaz.

| ID | Test adı | Doğrulanacak davranış | Geçme ölçütü |
|---|---|---|---|
| **L1** | `test_gdi_pixel_colors` | `screenshot(target="screen")` + hedef uygulama renk kareleri | Kırmızı `(255,0,0)`, yeşil `(0,255,0)`, mavi `(0,0,255)` merkez pikselleri birebir eşleşir |
| **L2** | `test_window_capture_size` | `screenshot(target="window:EDM Target")` | Yakalanan çerçeve boyutu `DWMWA_EXTENDED_FRAME_BOUNDS` ile birebir eşit |
| **L2b** | `test_uia_button_click` | `ui_elements` + `click(mark=...)` (`EDM-OK` düğmesi) | Düğme `Button` olarak bulunur, tıklama sonrası hedef log'unda düğme basımı görülür |
| **L3** | `test_occluded_window_uses_wgc_or_printwindow` | Üzeri ikinci bir Tk penceresiyle kısmen kapatılmış hedef | `backend != "gdi"` (`wgc` veya `printwindow`) seçilir ve hedef içindeki kırmızı kare pikseli doğru okunur |
| **L4** | `test_click_accuracy` | Önizleme (`pixel`) koordinatıyla tuvalde 5 farklı noktaya `click` | Hedef log'undaki fiziksel ekran koordinatları hedefle `±1 px` içinde |
| **L5** | `test_click_norm1000_accuracy` | `coord_space="norm1000"` ile `click` | Hedef log'undaki koordinat beklenen noktayla `±1 px` içinde |
| **L6** | `test_type_unicode` | Hedef `Entry` alanına `type_text("ğüşıöçİĞÜŞÖÇ 123 €")` | UIA `ValuePattern` ile geri okunan metin birebir aynı |
| **L7** | `test_drag_and_scroll` | Tuval üzerinde `drag` ve `scroll(dy=±3)` | Hedef log'unda başlangıç→bitiş sürükleme ve tekerlek delta kayıtları oluşur |
| **L8** | `test_find_text_turkish` | `find_text("Şüphe", target="window:EDM Target")` | Döndürülen dikdörtgen hedef etiketin gerçek konumuyla örtüşür |
| **L9** | `test_stale_after_move` | Gözlem al → `window_action("move")` → eski gözlemle `click` | `STALE_OBSERVATION` döner ve hedef log'unda sıfır tıklama olur |
| **L10** | `test_killswitch_mid_sequence` | `run_sequence` ortasında `Local\EDM_ABORT` olayı ayarlanır | Dizi anında kesilir, `ABORTED_BY_USER` döner, kalan adımlar çalışmaz |
| **L11** | `test_snip_driven_by_edm` | `edm snip` overlay'i başlar, EDM `drag(500,300 → 900,600)` çizer | Üretilen kullanıcı alıntısı gözleminin `frame_rect` değeri `±2 px` içinde tutar |

## 4. Gerçek uygulama doğrulama matrisi (M1–M7)

Kullanıcının masaüstünde (Faz 6 / `scripts/run-live-acceptance.ps1` + manuel ajan denemesi) doğrulanacak gerçek senaryolar:

| ID | Uygulama / Senaryo | Önerilen EDM stratejisi | Beklenen sonuç ve tuzak |
|---|---|---|---|
| **M1** | **AutoCAD** | Üst/komut işlemleri için klavye kısayolu veya komut satırı; küçük ribbon ikonlarında `screenshot` → `zoom` → `click` | DirectX tuval UIA'ya kapalıdır; GDI DWM bileşiğini görür. Boş kare çıkarsa `wgc`/`printwindow` yedeği devrede olmalı |
| **M2** | **WinRAR** | Toplu arşivde `rar.exe`/`unrar` CLI; GUI diyaloglarında `ui_elements` → `click(mark)` | Standart Win32 kontrolleri UIA ile yüksek isabet verir |
| **M3** | **Chrome** | Web sayfası içi DOM işleri için tarayıcı/DevTools MCP; işletim sistemi dosya seçme/indirme diyaloglarında `find_text` veya `ui_elements` | Saf pikselle web formu doldurmaya çalışmak yavaştır; doğru aracı seçmek esastır |
| **M4** | **AOC G-Menu** (yönetici yetkili araç) | Normal EDM oturumunda `ELEVATION_REQUIRED` uyarısı; kullanıcının UAC onayıyla yükselttiği EDM oturumunda `screenshot`/`zoom`/`click` | Windows UIPI normal süreç girdisini sessizce yutar; EDM sessizce başarısız olmamalı, açıkça bildirmeli |
| **M5** | **UAC / Kilit Ekranı** | `Win+L` veya UAC istemi sırasında çağrı | Asılı kalmadan `SESSION_LOCKED` veya `SECURE_DESKTOP` döner |
| **M6** | **Ölçekli Ekran (%125 / %150 DPI)** | Windows ölçeği > %100 iken `screenshot`, `zoom`, `click` | `SetProcessDpiAwarenessContext(-4)` sayesinde ±1 px doğruluk korunur |
| **M7** | **Türkçe Klavye + Pano Koruma** | TR-Q klavyede `press_keys` + `clipboard` testi | `VkKeyScanW` Türkçe karakterleri çözer; test sonrası önceki pano geri yüklenir |
