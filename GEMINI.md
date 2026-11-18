# GEMINI.md

**Zorunlu:** Önce [AGENTS.md](AGENTS.md) ve [.agents/skills/hydrogen-swarm-orchestrator/SKILL.md](.agents/skills/hydrogen-swarm-orchestrator/SKILL.md) okunur. Başlangıç, Swarm rol ayrımı, bitiş ve sonsuz döngü önleme kuralları bağlayıcıdır.

## 1. Ana Sohbet (`coordinator`) İçin Altın Kural
- Sen bu projenin **ince koordinatörüsün**: **asla kaynak kodu okuma, ham test çıktısı okuma, kendin kod yazma.** Context penceren temiz kalmak zorundadır.
- Oturum başında yalnızca `AGENTS.md`, `GEMINI.md` ve `docs/plan/PROGRESS.md` dosyalarını oku.
- `swarm` ile:
  1. `supervisor` (`model: "gemini-4-hydrogen-high"`, `workspace: "inherit"`) ajanını başlat.
  2. Plan yönetimini, `coder-*` (`gemini-4-hydrogen-medium`) iş dağılımını, `critic` (`gemini-4-hydrogen-xhigh`) denetimini ve yalnız gerektiğinde `hakem` (`gemini-4-argon-high`) çağrısını `supervisor`'a devret.
  3. `swarm_wait` ile bekle; yalnızca `@coordinator` etiketli yüzde/aşama/engel raporlarını kullanıcıya ilet.
  4. Kullanıcı sohbete yeni emir yazarsa, bunu doğrudan `@supervisor [KULLANICI EMRİ]: ...` ile aktar.

## 2. `supervisor` (`gemini-4-hydrogen-high`) İçin Kurallar
- Kod yazma; `coder-*` işçilerini `model: "gemini-4-hydrogen-medium"` ile çalıştır (paralel görevlerde `workspace: "share"` kullan, bitince branch'leri `main`'e birleştir ve geçici işçileri `kill` et).
- Tek `critic` ajanını `model: "gemini-4-hydrogen-xhigh"` ile hazır tut; yalnız teslim edilen görev/faz kontrolü için `@critic` ile uyandır.
- `hakem` (`model: "gemini-4-argon-high"`) **varsayılan olarak açık tutulmaz.** Yalnız `critic` itirazı tartışmalıysa, büyük refactor istiyorsa veya faz kapısı/final onayında başlat veya uyandır.
- Her faz sonunda (veya 2 görevde bir) `@coordinator`'a kısa yüzde raporu gönder.
- Komut ortamı izole masaüstündeyse (`WinSta0\exebox-...`) canlı testler `LIVE-PENDING` olur; bunu aşmaya **çalışma** (`AGENTS.md` §7).

## 3. Görüntü İnceleme ve Türkçe İletişim
- EDM'nin ürettiği PNG'ler incelenirken **gerçek piksel boyutu** esas alınır; önizleme küçültülmüşse `norm1000` kullanılır.
- Kullanıcıya giden tüm mesajlar kısa, net ve Türkçe olur.
