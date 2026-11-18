# GEMINI.md

**Zorunlu:** Önce [AGENTS.md](AGENTS.md) okunur. Oradaki başlangıç, bitiş ve döngü önleme kuralları bağlayıcıdır.

Gemini'ye özel notlar:
- Yürütme biçimi: Görevler aynı oturumda tek tek uygulanır (`executing-plans`). Faz sonunda bağımsız bir gözden geçirici alt ajan (`Model: inherit`) yalnız o fazın diff'ini [01-UYGULAMA-PLANI.md](docs/plan/01-UYGULAMA-PLANI.md)'ye göre denetler. Bulgular düzeltilir veya ADR'ye gerekçeyle yazılır. Gözden geçirme döngüsü en fazla 1 tur sürer.
- Görüntü inceleme: EDM'nin ürettiği PNG'ler dosya okuma aracıyla görüntülenebilir. Koordinat okurken görüntünün **gerçek piksel boyutu** esas alınır. Araç önizlemeyi küçültmüş olabilir, bu durumda `norm1000` tercih edilir.
- Antigravity komut ortamı izole masaüstündeyse canlı testler `LIVE-PENDING` olur. Bunu düzeltmeye **çalışma** (AGENTS.md §6).
- Kullanıcı Türkçe konuşur. Yanıtlar kısa ve kanıta dayalı olur.
