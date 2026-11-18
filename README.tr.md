# EDM — Everything Desktop on Me (Türkçe)

> [English Documentation (`README.md`)](README.md)

**EDM (`edm-desktop`)**, yapay zekâ kodlama ve otomasyon ajanlarına Windows masaüstünde yüksek çözünürlüklü görme (ekran, monitör, pencere, bölge, zincirleme `zoom`, UI Automation numaralı işaretler, çevrimdışı Windows OCR ve kullanıcı çizimli `edm snip`) ile insan gibi fare/klavye/çizim kontrolü sağlayan **MCP (`stdio` + loopback Streamable HTTP)** ve **CLI** aracıdır.

## Ne Yapar?

- **Gözlem-Bağlı Koordinat Sözleşmesi:** Her yakalama bir `observation_id` ve `ImageMapping` üretir (`pixel` ve `norm1000` `[0..1000]` uzayları); Per-Monitor-V2 DPI farkındalığıyla fiziksel ekran piksellerine `±1 px` hassasiyetle eşlenir.
- **Çoklu Yakalama Arka Ucu:** Görünür hedeflerde birincil GDI (`mss`) bileşik yakalama; örtülü pencerelerde (`visible_fraction < 0.98`) veya boş kare tespitinde otomatik olarak Windows Graphics Capture (`windows-capture`) ve `PrintWindow(PW_RENDERFULLCONTENT)` yedeklerine geçiş.
- **Çevrimdışı Algı:** `ui_elements` ile numaralı UIA kontrolleri (Set-of-Mark, 5 s zaman aşımı) ve `find_text` ile çevrimdışı Windows WinRT OCR (`tr-TR` Türkçe `İ/I` katlaması, küçük kırpmalarda otomatik 2× büyütme).
- **İnsan Gibi Girdi ve Güvenlik:** `click`, `move_mouse`, `drag` (20 ara adım), `draw_path` (≤200 nokta, CAD/fırça çizimi için opsiyonel Catmull-Rom yumuşatma), `mouse_button`, `key_state`, `scroll`, `type_text` (`KEYEVENTF_UNICODE`), `press_keys` (`VkKeyScanW`), `window_action`, `launch`, `wait_for`, `clipboard` ve `run_sequence`.
- **Sessiz Başarısızlık Yasağı:** Oturum sınıflandırması (`ISOLATED_DESKTOP`, `SECURE_DESKTOP`, `SESSION_LOCKED`), UIPI bütünlük düzeyi kontrolü (`ELEVATION_REQUIRED`), gözlem ömrü + pencere hareketi/modal popup + 24×24 piksel yama doğrulaması (`STALE_OBSERVATION`), süreçler arası `Local\EDM_INPUT_LOCK` ve acil durdurma (`Ctrl+Alt+Shift+F12` / `Local\EDM_ABORT` / `(0,0)` köşesi).

## Hızlı Kurulum (3 Komut)

```powershell
git clone https://github.com/smitelagwar/EDM.git C:\Users\hsyn\Desktop\EDM
uv tool install --editable C:\Users\hsyn\Desktop\EDM
edm doctor
```

## İstemci Entegrasyon Kılavuzları

- [Antigravity (`docs/integrations/antigravity.md`)](docs/integrations/antigravity.md)
- [Codex Desktop / CLI (`docs/integrations/codex.md`)](docs/integrations/codex.md)
- [Claude Code (`docs/integrations/claude-code.md`)](docs/integrations/claude-code.md)
- [Gemini CLI (`docs/integrations/gemini-cli.md`)](docs/integrations/gemini-cli.md)
- [Ajan Becerisi (`integrations/skills/edm-desktop/SKILL.md`)](integrations/skills/edm-desktop/SKILL.md)

## MCP Araçları (23) ve CLI Komutları

| MCP Aracı (`edm`) | CLI Alt Komutu | Açıklama |
|---|---|---|
| `doctor` | `edm doctor` | Ortam, masaüstü oturumu (`WinSta0\Default` vs `exebox`), DPI, monitör ve arka uç raporu |
| `list_monitors` | `edm monitors` | Fiziksel monitörler, DPI ve çalışma alanları |
| `list_windows` | `edm windows [--query Q]` | Z-sırasına göre görünür üst düzey pencereler |
| `screenshot` | `edm shot --target T` | `screen`, `monitor:N`, `window:Q` veya `region:x,y,w,h` yakalama |
| `zoom` | `edm zoom --obs ID --x X --y Y --w W --h H` | Alt bölgeyi 4×'e kadar büyütme (önce kayıpsız PNG) |
| `ui_elements` | `edm elements [--window Q]` | Etkileşimli UIA öğeleri + numaralı Set-of-Mark önizlemesi |
| `find_text` | `edm find-text QUERY` | Çevrimdışı Windows OCR metin arama (`contains`, `exact`, `regex`) |
| `click` | `edm click --obs ID --x X --y Y` | Adresli tıklama (`obs+xy`, `obs+mark`, `text` veya `screen`) |
| `move_mouse` | `edm move ...` | İmleci hedefe taşıma |
| `drag` | `edm drag --from-... --to-...` | İki adres arasında 20 ara noktalı sürükleme |
| `draw_path` | `edm draw-path --obs ID --points JSON` | Kesintisiz çok noktalı çizim yolu (≤200 nokta, Catmull-Rom) |
| `mouse_button` | `edm mouse-btn down\|up` | Fare düğmesini basılı tutma veya bırakma |
| `key_state` | `edm key-state KEY down\|up` | Tek tuşu basılı tutma veya bırakma |
| `scroll` | `edm scroll --dy N` | Hedef noktada dikey/yatay tekerlek kaydırma |
| `type_text` | `edm type --text "..."` | Düzen bağımsız Unicode metin yazımı (`KEYEVENTF_UNICODE`) |
| `press_keys` | `edm keys ctrl+s` | Klavye kısayol akorları (`VkKeyScanW` destekli) |
| `window_action` | `edm window Q ACTION` | `focus`, `minimize`, `maximize`, `restore`, `close`, `move`, `resize` |
| `launch` | `edm launch TARGET` | Dosya yolu, Başlat Menüsü `.lnk`, AUMID veya URL başlatma |
| `wait_for` | `edm wait KIND` | `change`, `stable`, `window`, `window_gone` veya `text` bekleme (≤60 s) |
| `clipboard` | `edm clip get\|set` | Windows panosu metin/görüntü okuma ve yazma |
| `run_sequence` | `edm seq --steps JSON` | Tek kilit altında ön-doğrulamalı çoklu adım dizisi (≤25 adım) |
| `request_user_region` | `edm snip [--prompt P]` | Ekranı dondurup kullanıcıya dikdörtgen seçtirme (`user_snip`) |
| `get_user_snips` | `edm snip --list` | Son kullanıcı alıntılarını listeleme |
| — | `edm prune` | 7 gün veya 2 GB sınırını aşan gözlemleri temizleme |
| — | `edm mcp` | MCP `stdio` sunucusunu başlatma |
| — | `edm serve-http` | Kullanıcı başlatmalı loopback (`127.0.0.1`/`::1`) Streamable HTTP MCP sunucusu |

## Güvenlik ve Gizlilik Uyarısı

- **Yakalama veya pano araçları çağrıldığında ekranda görünen her şey bağlı AI istemcisine / LLM sağlayıcısına iletilebilir.** Masaüstü kontrolü vermeden önce özel belgelerinizi, parolalarınızı ve belirteçlerinizi kapatın.
- Tüm ekran görüntüleri ve eylem günlükleri yalnızca `%LOCALAPPDATA%\EDM\` (`EDM_DATA_DIR`) altında tutulur (7 gün / 2 GB otomatik budama); **asla** repo içine yazılmaz.
- Loopback HTTP modu (`edm serve-http`) yalnızca `127.0.0.1` veya `::1` adresine bağlanır, `%APPDATA%\EDM\http-token` içindeki Bearer belirtecini zorunlu tutar ve loopback dışı `Origin` başlıklarını HTTP `403` ile reddeder.
- Ayrıntılı tehdit modeli ve acil durdurma mekanizması için [SECURITY.md](SECURITY.md) belgesine bakın.

## Bilinen Sınırlar

- **Yalnızca Windows 10/11** (`sys.platform == "win32"`, Python `>=3.12,<3.14`).
- **Güvenli masaüstü ve DRM:** UAC istemi (`Winlogon`), kilit ekranı, DRM korumalı videolar ve `WDA_EXCLUDEFROMCAPTURE` pencereleri kullanıcı kipinden yakalanamaz; EDM bunu `SECURE_DESKTOP`, `SESSION_LOCKED` veya `CAPTURE_BLANK` ile açıkça bildirir.
- **Yönetici yetkili pencereler (UIPI):** Normal (`medium`) bir EDM süreci yönetici (`high`) penceresine girdi gönderemez; `ELEVATION_REQUIRED` döner.
- **Windows 10 WGC sarı çerçevesi:** Windows 10 (`build < 22000`) üzerinde `windows-capture` yedeği devreye girdiğinde işletim sisteminin sarı yakalama çerçevesi kısa süre görünebilir.

## Lisans

[MIT Lisansı](LICENSE) altında yayımlanmıştır. Üçüncü taraf bildirimleri [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) içindedir.
