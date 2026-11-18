# AGENTS.md: EDM çalışma protokolü (tüm AI ajanları için zorunlu)

> EDM = **Everything Desktop on Me**. AI ajanlarına Windows masaüstünde yüksek çözünürlüklü görme ve insan gibi tam fare/klavye/çizim kontrolü veren MCP + CLI aracı.
> Bu dosya; **çoklu ajan (Swarm) orkestrasyonunu, nereden başlanacağını, ne zaman durulacağını ve sonsuz döngüye girmemek için uyulacak kuralları** tanımlar. Plandan önce gelir.

## 1. Çoklu ajan mimarisi (Swarm & kota tasarrufu)

Uygulama süreci tek sohbette context şişirmeden **4 katmanlı Swarm** düzeniyle yürütülür:

| Rol | Sabit Swarm adı | Model kimliği | Görev ve sınır |
|---|---|---|---|
| **İnce Koordinatör** | `coordinator` (Ana sohbet) | Kullanıcının seçtiği oturum modeli | **Kod yazmaz, uzun dosya/diff/log okumaz.** Yalnızca `supervisor`'dan gelen faz/yüzde özetlerini kullanıcıya aktarır ve kullanıcının yeni emirlerini `@supervisor`'a iletir. |
| **Plan Yöneticisi** | `supervisor` | `gemini-4-hydrogen-high` | Görevleri dağıtır, `workspace:"share"` dallarını `main`'e birleştirir, faz kapılarını çalıştırır, ilerleme yüzdesini hesaplayıp `@coordinator`'a bildirir. Uzun kodları bizzat yazmaz. |
| **Kodlayıcı İşçiler** | `coder-1`, `coder-2`, … | `gemini-4-hydrogen-medium` | Asıl işi yaparlar: TDD testleri, uygulama kodu, `ruff`/`mypy`/`pytest`. Paralel çalışırken `workspace:"share"` alır, bitince branch'ini commit'leyip `@supervisor`'a raporlar. |
| **Denetçi / Eleştirmen** | `critic` | `gemini-4-hydrogen-xhigh` | **Kod yazmaz.** Yalnız yapılan işi, diff'i, test kalitesini ve `00-TASARIM.md` uyumunu inceler; açıkları/hataları bulur ve **somut çözüm yolunu** söyler. |
| **Meta-Denetçi / Hakem** | `hakem` *(yalnız gerektiğinde açılır)* | `gemini-4-argon-high` | **Sürekli açık tutulmaz** (kota tasarrufu). Yalnızca: (a) `critic` ile `coder` arasında anlaşmazlık varsa, (b) `critic` ağır/riskli değişiklik istiyorsa (*"gerçekten gerekli mi?"*), veya (c) büyük faz kapısı / final kabulde halüsinasyon kontrolü gerektiğinde `supervisor` tarafından çağrılır. Kararı (`ONAY` / `DÜZELT` / `GEREKSİZ`) bağlayıcıdır. |

### Token ve kota tasarruf kuralları
1. **ASLA `@all` kullanma:** Her `@isim` bildirimi alıcı ajanı uyandırıp tur harcatır. Yalnızca sıradaki tek ajana `@isim` yaz.
2. **İnce koordinatör disiplini:** `coordinator` `swarm_wait{since: ...}` ile uyur (uyurken 0 token harcar). Ara yazışmalar yalnızca `#build` kanalında (veya `@supervisor`/`@coder-*`/`@critic` arasında) döner; `coordinator` yalnızca `@coordinator` etiketlendiğinde (faz/yüzde bildirimi, karar veya engel) uyanır.
3. **Argon (`gemini-4-argon-high`) yalnız ihtiyaçta:** Rutin her görevde çağrılmaz; yalnız `critic` bulgusu tartışmalıysa, büyük refactor istiyorsa veya faz kapısı onayında açılır/uyandırılır.
4. **İşçi yaşam döngüsü:** Paralel iş bitip branch `main`'e alındıktan sonra geçici `coder-2`/`coder-3` `kill` edilir ki beklemede kalabalık kalmasın.
5. **Kota biterse:** İşçiyi `kill` + `add` yapma; `swarm{action:"model", ...}` ile konuşma geçmişini koruyarak uygun yedek modele geçir ve kullanıcıya bildir.
6. **Swarm yoksa yedek:** Ortamda `swarm` aracı yoksa `agy` CLI (`$env:LOCALAPPDATA\agy\bin\agy.exe --model gemini-4-hydrogen-medium` / `gemini-4-hydrogen-xhigh` / `gemini-4-argon-high`) veya `invoke_subagent` ile aynı katmanlı akış uygulanır.

## 2. Okuma sırası (her oturumda)
1. Bu dosya (`AGENTS.md`), [.agents/skills/hydrogen-swarm-orchestrator/SKILL.md](.agents/skills/hydrogen-swarm-orchestrator/SKILL.md) ve rolüne göre [GEMINI.md](GEMINI.md).
2. [docs/plan/PROGRESS.md](docs/plan/PROGRESS.md): nerede ve hangi yüzdede olunduğunu gösterir.
3. `supervisor`, `critic`, `hakem` ve ilgili `coder`: [docs/plan/00-TASARIM.md](docs/plan/00-TASARIM.md) + [docs/plan/01-UYGULAMA-PLANI.md](docs/plan/01-UYGULAMA-PLANI.md)'deki kendi görev bölümü. *(Ana sohbet `coordinator` yalnızca `AGENTS.md`, `GEMINI.md` ve `PROGRESS.md`'yi okur!)*
4. Gerekirse [02-TEST-VE-KABUL.md](docs/plan/02-TEST-VE-KABUL.md), [DECISIONS.md](docs/plan/DECISIONS.md), [BLOCKERS.md](docs/plan/BLOCKERS.md).

## 3. Başlangıç protokolü
1. `supervisor`, `git status` ve `git log --oneline -5` ile çalışma ağacının temiz olduğunu doğrular. Yarım kalmış görev varsa ilgili testleri koşturarak durumu belirler.
2. `PROGRESS.md`'deki ilk işaretlenmemiş görev (veya plandaki paralel faz grubu) `coder-*` işçilerine dağıtılır. Tek istisna: görev `BLOCKED` ise ve sonraki görev ona bağımlı değilse (`Interfaces → Consumes`) bağımsız göreve geçilir.
3. İlk oturumda `PROGRESS.md` içindeki "Ortam" bölümü bir kez doldurulur; Faz 1 sonrasında `uv run edm doctor` → `session.state` yazılır.

## 4. Görev döngüsü (TDD)
Her görev için (`coder`): testi yaz → çalıştır, **FAIL** gör → minimum kodu yaz → çalıştır, **PASS** gör → `ruff check`, `ruff format --check`, `mypy` → commit → `@supervisor`'a diff özeti + test çıktısı ile raporla.
- `supervisor`, `critic` (`gemini-4-hydrogen-xhigh`) onayını aldıktan sonra `PROGRESS.md` kutusunu + `%` oranını günceller (gerekirse `hakem` onayı alır).
- Commit mesajı plandaki gibidir (Conventional Commits).
- PROGRESS satırına commit kısa hash'i ve tek cümlelik not eklenir.

## 5. Bitiş koşulları (kesin)
| Seviye | Bitti sayılır | Sonra |
|---|---|---|
| Görev | Plandaki tüm adımlar ✓, testler yeşil, `critic` (ve gerekirse `hakem`) onaylı, commit atıldı | Sıradaki görev + `PROGRESS.md` yüzde güncelle |
| Faz | Faz kapısı komutları yeşil, canlı testler PASS **veya** `LIVE-PENDING` kaydedildi | `git push origin main`, `@coordinator`'a `%` raporu gönder, sıradaki faz |
| Proje | T6.3 tamam **veya** kalan her görev BLOCKED/LIVE-PENDING | `FINAL-REPORT.md` → etiket → push → `@coordinator` son raporu → **DUR** |

**DUR şu anlama gelir:** Yeni özellik, refactor, "küçük iyileştirme" veya `IDEAS.md` maddesi başlatılmaz. Kullanıcıya final rapor bağlantısı verilir ve Swarm kapatılır.

## 6. Döngü önleme kuralları (ihlal = görev iptal)
1. **3 deneme kuralı:** Aynı başarısız test veya komut için en fazla 3 düzeltme denemesi yapılır. Her deneme **farklı bir hipotezle** yapılır ve hipotez `PROGRESS.md`'ye tek satır yazılır. 3. denemeden sonra görev `BLOCKED` olur, [BLOCKERS.md](docs/plan/BLOCKERS.md)'ye kayıt düşülür (belirti, denenen 3 hipotez, son hata çıktısı, önerilen sonraki adım) ve bağımsız göreve geçilir.
2. **Aynı komutu aynı girdiyle tekrar çalıştırma.**
3. **Araştırma sınırı:** Bir engel için en fazla 3 web araması ve 5 belge okuması yapılır. Sonra karar verilir ve [DECISIONS.md](docs/plan/DECISIONS.md)'ye ADR yazılır.
4. **Kontrol noktası:** Bir görevde `coder` 40 araç çağrısı aşarsa durur, `supervisor`'a rapor verir; gerekirse görev ikiye bölünür.
5. **Kapsam kilidi:** Planda olmayan iş yapılmaz. Fikirler [IDEAS.md](docs/plan/IDEAS.md)'ye tek satırla yazılır, uygulanmaz.
6. **Plan çelişkisi:** Kurulu kütüphane gerçekliği planla çelişirse gerçekliğe uyulur, `DECISIONS.md`'ye ADR ve plana not düşülür.
7. **Bekleme yasağı:** Uyku/tekrar döngüsüyle "belki düzelir" beklemesi yapılmaz; her bekleme zaman aşımıyla sınırlıdır.

## 7. Canlı (masaüstü) testler: özel kural
- Antigravity komut ortamı izole masaüstünde (`WinSta0\exebox-…`) çalışabilir. Orada GDI ekranı boştur, kullanıcının pencereleri görünmez.
- `live` testler `require_interactive` fiksürüyle kendiliğinden atlanır (`LIVE-PENDING: isolated_desktop`). Bu **başarısızlık değildir**. `PROGRESS.md`'ye `LIVE-PENDING` yazılır ve devam edilir.
- **Kesin yasak:** `SwitchDesktop`, `SetThreadDesktop`, `OpenDesktopW` ile masaüstü değiştirme. Sandbox/host yaması. İzole ortamdan kullanıcı masaüstüne köprü kurmak için `edm serve-http`'yi kendi başına başlatmak veya istemci yapılandırmasını değiştirmek. UAC atlatma.
- Canlı kabul en sonda kullanıcı tarafından `scripts/run-live-acceptance.ps1` ile kendi masaüstünde koşulur.

## 8. Bağımlılık izin listesi
Çalışma zamanı: `mcp`, `mss`, `pillow`, `comtypes`, `uiautomation`, `windows-capture`, `winrt-runtime` + `winrt-Windows.*` (OCR için gerekenler). Geliştirme: `pytest`, `pytest-timeout`, `hypothesis`, `ruff`, `mypy`.
Listede olmayan paket eklenmeden önce ADR yazılır (neden, lisans, alternatif). GPL/AGPL lisanslı paket **eklenmez**. Başka repodan kod alınırsa lisansı doğrulanır (MIT/BSD/Apache) ve `THIRD_PARTY_NOTICES.md`'ye kaynak eklenir.

## 9. Komut hijyeni (Windows PowerShell)
- Her komutun bir zaman sınırı vardır (`pytest --timeout`, alt süreçler `timeout=`).
- Etkileşimli komut çalıştırılmaz (`git rebase -i`, editör açan komutlar).
- Çok satırlı `python -c "…"` yazılmaz. Gerekirse geçici betik `%TEMP%` altına yazılıp çalıştırılır ve sonra silinir.
- Çıplak `curl` kullanılmaz; gerekirse `curl.exe --max-time 10` kullanılır.
- Uzun çalışan süreç (MCP sunucusu, hedef test uygulaması) yalnız testin içinde ve teardown ile başlatılır.
- Kullanıcının panosu, açık pencereleri ve dosyaları testlerde kalıcı olarak değiştirilmez.

## 10. Git kuralları
- Dal: `main`. Her görev = 1 commit. Her faz sonu = `git push origin main`.
- **Yasak:** `--force` push, geçmiş yeniden yazma, `git add -A` ile kör ekleme (`git add <dosyalar>` kullanılır), ekran görüntüsü/günlük/`%LOCALAPPDATA%` verisi veya HTTP belirteci commit etmek.

## 11. Kullanıcıya ne zaman sorulur?
Yalnızca: (a) UAC/kimlik/izin gerektiren gerçek bir engel, (b) geri dönüşü olmayan işlem (kullanıcı dosyası silme, istemci yapılandırması yazma), (c) tasarımla çözülemeyen ve ürün davranışını değiştiren çelişki. Diğer her şeyde `supervisor` (+ gerekirse `hakem`) karar verir ve `DECISIONS.md`'ye yazar.

## 12. Raporlama biçimi
- `PROGRESS.md` satırı: `- [x] T2.3 Gözlem deposu — a1b2c3d — 9 test yeşil; prune bayt sınırı testi eklendi.`
- `supervisor → @coordinator` durum bildirimi (yalnız kısa özet):
  `[DURUM %41 | 11/27] Faz 2 tamamlandı (L1–L3 LIVE-PENDING). Sıradaki: Faz 3 (T3.1+T3.2+T3.3 paralel).`
