# EDM — Everything Desktop on Me

> Yapay zekâ ajanları (Antigravity, Codex Desktop, Claude Code, Gemini CLI/`agy` ve betikler) için Windows masaüstünde yüksek çözünürlüklü görme, pencere/dikdörtgen ekran alıntısı, zoom, UIA/OCR algılama ve tam fare/klavye kontrolü sağlayan **MCP + CLI** aracı.

> **Durum:** Tasarım ve uygulama planı tamamlandı (`v0.1` uygulamaya hazır; `src/edm` kodlaması Faz 0 ile başlar).  
> **English:** [README.md](README.md) · **Tasarım:** [docs/plan/00-TASARIM.md](docs/plan/00-TASARIM.md)

---

## Neden EDM?

Yapay zekâ AutoCAD, WinRAR, Chrome veya AOC G-Menu gibi masaüstü programlarını yönetmeye çalışırken çoğu zaman ilk denemelerde başarısız olup döngüye girer:
1. **Pencereye bağlanma kırılganlığı:** Pencere hedefli yakalamalar (`WGC` / `PrintWindow`) DirectX/OpenGL çizim alanlarında, açılış ekranlarında, sağ tık menülerinde veya tepsi pencerelerinde zaman aşımına ya da siyah ekrana düşer.
2. **UIA körlüğü:** Standart Windows diyalogları erişilebilirlik ağacında görünür; fakat CAD çizim alanı ve özel donanım arayüzleri boş kutu gibi görünür.
3. **DPI ve yüksek çözünürlük kayması:** %125/%150 ölçekli veya 2K/4K ekranlarda küçültülmüş tam ekran görüntüsünden piksel tahmini yapmak küçük ikonları ıskalar.
4. **Sessiz OS engelleri (UIPI ve izole masaüstü):** Yönetici yetkili programlar normal süreçten gelen `SendInput` girdisini sessizce yutar; korumalı ajan kabukları ise kullanıcının `WinSta0\Default` masaüstü yerine izole bir masaüstünde çalışabilir.

**EDM buna gözlem-tabanlı, PrtSc öncelikli, kapalı döngü bir mimariyle çözüm getirir:**
- **Ekranda ne varsa gör:** Tam ekran, monitör, görünür pencere (GDI DWM bileşiği) veya dikdörtgen bölge yakalama; örtülü pencerelerde WGC / `PrintWindow` yedekleri ve otomatik boş kare tespiti.
- **Genelden özele `zoom`:** Tam ekranı gördükten sonra yoğun araç çubuğu veya küçük düğmeyi orijinal çözünürlükte (4×'e kadar, küçük CAD kırpmalarında kayıpsız PNG) yakınlaştır; EDM koordinatları fiziksel sanal ekrana (`pixel` veya `norm1000`) otomatik çevirir.
- **İnsan gibi tam fare/klavye ve çizim kontrolü:** Tıklama, sürükleme, kesintisiz çok noktalı/eğri çizim (`draw_path`), tuş/fare basılı tutma (`mouse_button`, `key_state` + hata anında otomatik bırakma), Unicode yazma ve çok adımlı sıralı eylemler.
- **Kullanıcı alıntısı (`edm snip`):** Dilediğinde ekranı dondurup dikdörtgeni kendin çiz, ajan doğrudan o bölge üzerinden çalışsın.
- **Kapalı döngü güvenlik:** Per-Monitor-V2 DPI kilidi, UIPI tespiti (`ELEVATION_REQUIRED`), eylem öncesi 24×24 piksel yama ve pencere geometrisiyle eski-gözlem (stale) koruması, ajanlar arası girdi kilidi ve anlık acil durdurma (`Ctrl+Alt+Shift+F12` + `(0,0)` köşe).

---

## Planlama ve Ajan Dokümanları

- [AGENTS.md](AGENTS.md) — Başlangıç, bitiş, TDD ve sonsuz döngü önleme kuralları
- [GEMINI.md](GEMINI.md) — Gemini uygulaması için faz ve görüntü inceleme kuralları
- [docs/plan/00-TASARIM.md](docs/plan/00-TASARIM.md) — Mimari tasarım, koordinat sözleşmesi, 20 MCP aracı ve hata kodları
- [docs/plan/01-UYGULAMA-PLANI.md](docs/plan/01-UYGULAMA-PLANI.md) — Faz 0'dan Faz 6'ya adım adım uygulama planı
- [docs/plan/02-TEST-VE-KABUL.md](docs/plan/02-TEST-VE-KABUL.md) — Kalite kapıları, canlı kabul (`L1–L11`) ve uygulama matrisi (`M1–M7`)
- [docs/plan/PROGRESS.md](docs/plan/PROGRESS.md) — Görev ilerleme panosu
- [docs/plan/DECISIONS.md](docs/plan/DECISIONS.md) — Mimari karar defteri (ADR)

---

## Gizlilik ve Güvenlik

- Ekran görüntüleri ve eylem günlükleri yalnızca yerel `%LOCALAPPDATA%\EDM\` klasöründe tutulur (7 gün / 2 GB sınırı) ve asla Git deposuna işlenmez.
- Dış ağ çağrısı ve telemetri yoktur.
- EDM masaüstü izolasyonunu veya UAC'yi asla atlatmaz; yönetici yetkili pencere algıladığında `ELEVATION_REQUIRED` hatası ile kullanıcıyı açıkça bilgilendirir.

---

## Teşekkür

EDM mimarisi, açık kaynak bilgisayar-kullanımı (Computer Use) ekosistemindeki fikirler ve kullanıcının kendi yerel Win32 masaüstü otomasyonu (`muhendis-mimar-portali/scripts/idecad/desktop.py`) deneyiminden öğrenilen dersler üzerine sıfırdan tasarlanmıştır. İncelenen repolar için bkz. [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Lisans

[MIT](LICENSE) © 2026 Hüseyin Günaydın
