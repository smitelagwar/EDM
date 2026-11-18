# AGENTS.md: EDM çalışma protokolü (tüm AI ajanları için zorunlu)

> EDM = **Everything Desktop on Me**. AI ajanlarına Windows masaüstünde yüksek çözünürlüklü görme ve fare/klavye kontrolü veren MCP + CLI aracı.
> Bu dosya; **nereden başlanacağını, ne zaman durulacağını ve döngüye girmemek için uyulacak kuralları** tanımlar. Plandan önce gelir.

## 1. Okuma sırası (her oturumda)
1. Bu dosya.
2. [docs/plan/PROGRESS.md](docs/plan/PROGRESS.md): nerede kalındığını gösterir.
3. [docs/plan/00-TASARIM.md](docs/plan/00-TASARIM.md): neyin neden yapıldığını anlatır.
4. [docs/plan/01-UYGULAMA-PLANI.md](docs/plan/01-UYGULAMA-PLANI.md): yalnız sıradaki görevin bölümü okunur.
5. Gerekirse [02-TEST-VE-KABUL.md](docs/plan/02-TEST-VE-KABUL.md), [DECISIONS.md](docs/plan/DECISIONS.md), [BLOCKERS.md](docs/plan/BLOCKERS.md).

## 2. Başlangıç protokolü
1. `git status` ve `git log --oneline -5` ile çalışma ağacının temiz olduğu doğrulanır. Temiz değilse önce PROGRESS'teki son not okunur. Yarım kalmış görev varsa o görevin testleri çalıştırılarak durum belirlenir.
2. PROGRESS'teki **ilk işaretlenmemiş görev** seçilir. Sıra atlanmaz. Tek istisna: bir görev BLOCKED ise ve sonraki görev ona bağımlı değilse (Interfaces → Consumes) sonraki göreve geçilebilir.
3. Oturumun ilk görevinde PROGRESS'in "Ortam" bölümü boşsa bir kez doldurulur. Faz 1 sonrasında `uv run edm doctor` → `session.state` değeri yazılır.

## 3. Görev döngüsü (TDD)
Her görev için: testi yaz → çalıştır, **FAIL** gör → minimum kodu yaz → çalıştır, **PASS** gör → `ruff check`, `ruff format`, `mypy` → PROGRESS'te kutuyu işaretle → **tek commit**.
- Commit mesajı plandaki gibidir (Conventional Commits).
- PROGRESS satırına commit kısa hash'i ve bir cümlelik not eklenir.

## 4. Bitiş koşulları (kesin)
| Seviye | Bitti sayılır | Sonra |
|---|---|---|
| Görev | Plandaki tüm adımlar ✓, testler yeşil, commit atıldı | Sıradaki görev |
| Faz | Faz kapısı komutları yeşil, canlı testler PASS **veya** `LIVE-PENDING` olarak kaydedildi | `git push origin main`, PROGRESS'e faz özeti, sıradaki faz |
| Proje | T6.3 tamam **veya** kalan her görev BLOCKED/LIVE-PENDING | `FINAL-REPORT.md` → etiket → push → **DUR** |

**DUR şu anlama gelir:** Yeni özellik, refactor, "küçük iyileştirme" veya IDEAS.md maddesi başlatılmaz. Kullanıcıya rapor bağlantısı verilir ve oturum biter.

## 5. Döngü önleme kuralları (ihlal = görev iptal)
1. **3 deneme kuralı:** Aynı başarısız test veya komut için en fazla 3 düzeltme denemesi yapılır. Her deneme **farklı bir hipotezle** yapılır ve hipotez PROGRESS'e tek satır yazılır. 3. denemeden sonra görev `BLOCKED` olur, [BLOCKERS.md](docs/plan/BLOCKERS.md)'ye kayıt düşülür (belirti, denenen 3 hipotez, son hata çıktısı, önerilen sonraki adım). Bağımsız göreve geçilir.
2. **Aynı komutu aynı girdiyle tekrar çalıştırma.** Çıktı değişmediyse tekrar bilgi vermez.
3. **Araştırma sınırı:** Bir engel için en fazla 3 web araması ve 5 belge okuması yapılır. Sonra karar verilir ve [DECISIONS.md](docs/plan/DECISIONS.md)'ye ADR yazılır.
4. **Kontrol noktası:** Bir görevde 40 araç çağrısı aşılırsa durulur. PROGRESS'e "nerede, neden uzadı" yazılır. Kapsam büyüdüyse görev ikiye bölünür (PROGRESS'e alt madde olarak eklenir).
5. **Kapsam kilidi:** Planda olmayan iş yapılmaz. Fikirler [IDEAS.md](docs/plan/IDEAS.md)'ye bir satırla yazılır, uygulanmaz.
6. **Plan çelişkisi:** Plan ile kurulu kütüphane gerçekliği çelişirse gerçekliğe uyulur. Plan sessizce değiştirilmez: DECISIONS.md'ye ADR yazılır, gerekirse plandaki ilgili satır güncellenir ve aynı commit'e eklenir.
7. **Bekleme yasağı:** Bir sonucu "belki şimdi olur" diye uyku/tekrar döngüsüyle bekleme yapılmaz. Her bekleme bir zaman aşımı ile sınırlıdır.

## 6. Canlı (masaüstü) testler: özel kural
- Antigravity'nin komut ortamı izole bir masaüstünde (`WinSta0\exebox-…`) çalışabilir. Orada GDI ekranı boştur, kullanıcının pencereleri görünmez.
- `live` testler `require_interactive` fiksürüyle kendiliğinden atlanır (`LIVE-PENDING: isolated_desktop`). Bu **başarısızlık değildir**. PROGRESS'e `LIVE-PENDING` yazılır ve devam edilir.
- **Kesin yasak:** `SwitchDesktop`, `SetThreadDesktop`, `OpenDesktopW` ile masaüstü değiştirme. Sandbox/host yaması. İzole ortamdan kullanıcı masaüstüne köprü kurmak için `edm serve-http`'yi kendi başına başlatmak veya istemci yapılandırmasını değiştirmek. UAC atlatma.
- Canlı kabul en sonda kullanıcı tarafından `scripts/run-live-acceptance.ps1` ile kendi masaüstünde koşulur.

## 7. Bağımlılık izin listesi
Çalışma zamanı: `mcp`, `mss`, `pillow`, `comtypes`, `uiautomation`, `windows-capture`, `winrt-runtime` + `winrt-Windows.*` (OCR için gerekenler). Geliştirme: `pytest`, `pytest-timeout`, `hypothesis`, `ruff`, `mypy`.
Listede olmayan paket eklenmeden önce ADR yazılır (neden, lisans, alternatif). GPL/AGPL lisanslı paket **eklenmez**. Başka repodan kod alınırsa lisansı doğrulanır (MIT/BSD/Apache) ve `THIRD_PARTY_NOTICES.md`'ye kaynak eklenir.

## 8. Komut hijyeni (Windows PowerShell)
- Her komutun bir zaman sınırı vardır. pytest `--timeout` kullanır. Alt süreçler `timeout=` ile çalışır.
- Etkileşimli komut çalıştırılmaz (girdi bekleyen istemler, `git rebase -i`, editör açan komutlar).
- Çok satırlı `python -c "…"` yazılmaz. Gerekirse geçici betik `%TEMP%` altına yazılıp çalıştırılır ve sonra silinir.
- Çıplak `curl` kullanılmaz (PowerShell alias'ı). Gerekirse `curl.exe --max-time 10` kullanılır.
- Uzun çalışan süreç (MCP sunucusu, hedef test uygulaması) yalnız testin içinde ve teardown ile başlatılır. Elle başlatıldıysa iş bitince öldürülür.
- Kullanıcının panosu, açık pencereleri ve dosyaları testlerde kalıcı olarak değiştirilmez (pano testi eski içeriği geri yükler).

## 9. Git kuralları
- Dal: `main` (kişisel repo, deploy yok). Her görev = 1 commit. Her faz sonu = `git push origin main`.
- **Yasak:** `--force` push, geçmiş yeniden yazma, `git add -A` ile kör ekleme (`git add <dosyalar>` kullanılır), ekran görüntüsü/günlük/`%LOCALAPPDATA%` verisi commit etmek.
- Gizli bilgi (token, parola) commit edilmez. HTTP belirteci yalnız `%APPDATA%\EDM\http-token` içinde tutulur.

## 10. Kullanıcıya ne zaman sorulur?
Yalnızca: (a) UAC/kimlik/izin gerektiren gerçek bir engel, (b) geri dönüşü olmayan işlem (kullanıcı dosyası silme, istemci yapılandırması yazma), (c) tasarımla çözülemeyen ve ürün davranışını değiştiren çelişki. Diğer her şeyde makul karar verilir ve ADR'ye yazılır. Soru tek mesajda, seçenekli ve önerili sorulur.

## 11. Raporlama biçimi (PROGRESS satırı)
`- [x] T2.3 Gözlem deposu — a1b2c3d — 9 test yeşil; prune bayt sınırı testi eklendi.`
`- [!] T2.2 … — BLOCKED — bkz. BLOCKERS#B-002`
`- [~] L3 … — LIVE-PENDING (isolated_desktop)`
