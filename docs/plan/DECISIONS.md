# Mimari Karar Defteri (ADR — Architectural Decision Records)

> Biçim: `[DURUM] [TARİH] [ADR-XXX] Başlık` · Durumlar: `AKTİF` | `YERİNE GEÇTİ` | `ERTELENDİ`

---

### [AKTİF] [2026-11-18] [ADR-001] Çekirdek dili ve bağımlılık yaklaşımı: Python 3.12 + ctypes Win32
- **Karar:** Çekirdek Python 3.12 (`>=3.12,<3.14`) üzerinde sıfırdan saf Python + `ctypes` Win32 API bağlarıyla yazılır; mevcut açık kaynak MCP sunucuları (örn. `Windows-MCP`) fork edilmez, yalnız mimari fikir kaynağı olarak incelenir.
- **Gerekçe:** `winrt-*`, `windows-capture` ve `mcp` tekerleklerinin en olgun desteği Python 3.12'dedir. Kendi çekirdeğimiz sayesinde gözlem-bağlı koordinat sözleşmesi, 24×24 stale koruması ve `EDM_FAKE=1` test edilebilirliği temiz biçimde tasarlanır.
- **Alternatifler:** (1) `Windows-MCP` fork'u → kendi koordinat/stale/guard sözleşmemizi sonradan yamalamak daha kırılgan; (2) Rust/C# servis → geliştirme ve test maliyeti yüksek (v0.2+ sıcak yollar için açık bırakıldı).

### [AKTİF] [2026-11-18] [ADR-002] Yakalama stratejisi: GDI (`mss`) birincil, WGC ve PrintWindow yedek; DXGI v0.1 dışı
- **Karar:** Masaüstü, monitör, bölge ve açık/görünür pencereler (`visible_fraction >= 0.98`) için birincil arka uç GDI ekran yakalamadır (`mss` + `DWMWA_EXTENDED_FRAME_BOUNDS` kırpması). Örtülü pencerelerde veya boş kare tespitinde sırasıyla WGC (`windows-capture`) ve `PrintWindow(PW_RENDERFULLCONTENT)` denenir. DXGI Desktop Duplication v0.1'e alınmamıştır.
- **Gerekçe:** DWM bileşik ekranı AutoCAD'in DirectX görünüm alanını, sağ tık menülerini ve tepsi açılır pencerelerini doğal olarak içerir; WGC tek pencere yakalaması ise geçmiş ölçümlerde (`FrameArrived timed out`) kırılgan görülmüştür. Ayrıca kullanıcının makinesi hibrit GPU'lu (RTX 4060 + AMD Radeon iGPU) olduğundan DXGI Desktop Duplication `DXGI_ERROR_UNSUPPORTED` üretebilir.
- **Bilinen etki:** Windows 10 (build 19045) üzerinde WGC yedeği devreye girdiğinde pencere etrafında kısa süreli sarı yakalama çerçevesi görünebilir; `windows-capture` `draw_border=False` desteklemezse `draw_border=None` yedeğine düşülür.

### [AKTİF] [2026-11-18] [ADR-003] Gözlem-bağlı koordinat sözleşmesi (`pixel` + `norm1000`) ve zincirleme `zoom`
- **Karar:** Ajan eylem koordinatları varsayılan olarak ham ekran pikselinde değil, bir `observation_id` ve `ImageMapping` nesnesine bağlı `pixel` veya `norm1000` (0–1000) uzayında verilir; fiziksel sanal ekran koordinatına EDM çevirir. `zoom` aracı yeni bir alt gözlem üretir ve çok adımlı yakınlaştırmalarda kök ekrana eksiksiz geri eşlenir.
- **Gerekçe:** 2560×1440 (veya 4K) tam ekran görüntüsü LLM'e küçültülerek (1600 px) gönderildiğinde ajan ile ekran pikselleri farklı ölçekte olur; ayrıca AutoCAD gibi yoğun araç çubuklarında `ScreenSpot-Pro` / `ZoomClick` bulgularına göre tek tam ekranla piksel tahmini yüksek hata verir.

### [AKTİF] [2026-11-18] [ADR-004] Eylem güvenliği: Tam kontrol + sessiz başarısızlık yasağı (Stale, UIPI, KillSwitch)
- **Karar:** Kullanıcının açık tercihi doğrultusunda kullanıcı onay kapısı konmaz (tam kontrol). Buna karşılık sessizce yanlış yere tıklamayı önlemek için her girdiden önce: (1) oturum kontrolü (`WinSta0\Default`), (2) acil durdurma (`Ctrl+Alt+Shift+F12` / `Local\EDM_ABORT` / `(0,0)` köşesi), (3) hedef sürecin bütünlük düzeyi kontrolü (UIPI / `ELEVATION_REQUIRED`), (4) gözlem yaşı + pencere geometrisi + 24×24 piksel yama değişimi (`STALE_OBSERVATION`), (5) `Local\EDM_INPUT_LOCK` kilidi zorunludur.
- **Gerekçe:** Hata üretmek, yanlış düğmeye basmaktan ucuzdur. Yönetici yetkili uygulamalarda (örn. AOC G-Menu) `SendInput` sessizce yutulduğu için EDM bunu kullanıcıya açıkça raporlar; UAC/desktop atlatma kesinlikle yapılmaz.

### [AKTİF] [2026-11-18] [ADR-005] Çevrimdışı algı katmanı: Windows UIA + Windows WinRT OCR (`tr-TR`)
- **Karar:** Görsel koordinattan önce ucuz ve deterministik katmanlar olarak `uiautomation` (Set-of-Mark numaralı kutular, 5 s zaman aşımı) ve yerel WinRT `Windows.Media.Ocr` (Türkçe `tr_fold` eşleşmesi, küçük görüntülerde 2× büyütme) sunulur. OmniParser/YOLO/Florence-2 v0.1'de yok (v0.2+ fikri).
- **Gerekçe:** Büyük yapay zekâ ağırlıkları indirmeden tamamen yerel ve hızlı çalışır; WinRAR/standart diyaloglarda UIA, özel çizimli menülerde OCR + Zoom kombinasyonu yeterlidir.

### [AKTİF] [2026-11-18] [ADR-006] Çift kabuklu MCP mimarisi: stdio + kullanıcı başlatmalı loopback HTTP
- **Karar:** Tüm yetenekler tek `service.Edm` katmanında toplanır; üzerinde `edm mcp` (stdio) ve kullanıcı başlatmalı `edm serve-http` (`127.0.0.1`/`::1`, Bearer token + Origin kontrolü) sunulur. Uygulayıcı ajan izole masaüstünü aşmak için HTTP modunu kendi başına başlatmaz veya istemci yapılandırmasını yazmaz.
- **Gerekçe:** Antigravity, Codex Desktop, Claude Code ve Gemini CLI aynı aracı kullanabilmelidir. Antigravity komut ortamı `WinSta0\exebox-...` içinde kaldığında kullanıcı isterse kendi etkileşimli masaüstünde `edm serve-http` (veya küresel MCP kaydı) ile köprü kurar.

### [AKTİF] [2026-11-18] [ADR-007] Veri gizliliği ve Git hijyeni
- **Karar:** Tüm ekran görüntüleri ve eylem günlükleri yalnız `%LOCALAPPDATA%\EDM\` altında tutulur (7 gün / 2 GB otomatik budama), asla repo içine yazılmaz veya Git'e eklenmez. Loopback HTTP belirteci `%APPDATA%\EDM\http-token` içinde kalır.
- **Gerekçe:** Repo public (`smitelagwar/EDM`) olacağından kullanıcının ekran görüntüleri, pano içerikleri ve belirteçleri asla uzak depoya sızmamalıdır.

### [AKTİF] [2026-11-18] [ADR-008] Görsel düzen ve üçüncü taraf esinlenmeler
- **Karar:** Yalnızca MIT/BSD/Apache uyumlu bağımlılıklar eklenir (GPL/AGPL yasak). Açık kaynak GUI ajanı repolarından alınan mimari fikirler [../../THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md) içinde belgelenir; kaynak kod doğrudan kopyalanmaz (temiz oda yazımı).
- **Gerekçe:** Temiz lisans yönetimi ve sürdürülebilirlik.
