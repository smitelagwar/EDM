---
name: hydrogen-swarm-orchestrator
description: Use when orchestrating multi-phase coding or build projects with a thin main-chat coordinator, a Gemini 4 Hydrogen High supervisor, Gemini 4 Hydrogen Medium coder workers, a Gemini 4 Hydrogen XHigh critic, and an on-demand Gemini 4 Argon High meta-judge while strictly minimizing token/quota burn and preventing infinite loops.
---

# Hydrogen Swarm Orchestrator

4 katmanlı, kota tasarruflu ve çapraz denetimli çoklu ajan uygulama protokolü. Ana sohbeti temiz tutar, kodlamayı ucuz işçilere dağıtır, kaliteyi eleştirmen ve yalnız gerektiğinde açılan hakemle güvenceye alır.

## 1. Rol ve Model Sözleşmesi

| Swarm Üyesi | Model (`swarm` / `agy`) | Workspace | Sorumluluk ve Sınır |
|---|---|---|---|
| `coordinator` (Ana sohbet) | Oturum modeli | `inherit` | **Kod yazmaz, kaynak kod/ham log/uzun diff okumaz.** Yalnız varsa `PROJECT.md`, `AGENTS.md`, `GEMINI.md`, `PROGRESS.md` (veya plan özeti) okur; `supervisor`'ı kurar, `swarm_wait{since: N}` ile bekler, kullanıcıya kısa `[DURUM %XX \| N/M]` özetini iletir ve yeni kullanıcı emirlerini `@supervisor`'a aktarır. |
| `supervisor` | `gemini-4-hydrogen-high` | `inherit` | Planı ve görev bağımlılıklarını yönetir; işleri `coder-*` işçilerine böler, paralel `share` dallarını `main`'e birleştirir, kapı testlerini koşar, `%` ilerlemeyi hesaplar. Kendisi uzun kod yazmaz. |
| `coder-1`, `coder-2`, … | `gemini-4-hydrogen-medium` | Tek işte `inherit`, paralelde `share` | Asıl işi yapar: TDD (önce başarısız test → minimum kod → geçiş → proje kalite kapıları), commit atar ve `@supervisor`'a diff + gerçek test çıktısı sunar. |
| `critic` | `gemini-4-hydrogen-xhigh` | `inherit` | **Kod yazmaz (salt-okunur).** Diff'i, testlerin gerçekliğini (uydurma/yüzeysel assert var mı) ve tasarım sözleşmesini kontrol eder; açık bulursa **somut çözüm yolunu** söyler. |
| `hakem` *(yalnız ihtiyaçta)* | `gemini-4-argon-high` | `inherit` | **BAŞTA AÇILMAZ.** Yalnız ilk kez: (1) `critic` ile `coder` anlaşmazlığa düştüğünde, (2) `critic` ağır/riskli refactor istediğinde (*"gerçekten gerekli mi?"*), veya (3) büyük faz kapısı / final kabulde `supervisor` tarafından `swarm{action:"add"}` ile açılır. Bağlayıcı karar (`ONAY` / `DÜZELT` / `GEREKSİZ`) verir; ardından `waiting` kalır (0 token) ve yalnız sonraki uyuşmazlık/kapıda `@hakem` ile uyandırılır. |

> **Araç Uyumu:** Antigravity'de kesin model kimlikleri `swarm{action:"add", model:"..."}` veya `agy --model ...` ile verilir. `invoke_subagent` yalnızca `inherit | flash_lite | flash | pro` kabul ettiği için tam model/seviye seçiminde `swarm` birincildir.

## 2. Başlangıç Akışı (Ana Sohbet)

1. Ana sohbet varsa yalnız plan özetini (`PROJECT.md`, `AGENTS.md`, `GEMINI.md`, `PROGRESS.md`) okur; `PROGRESS.md` henüz yoksa `supervisor`'a ilk adım olarak oluşturmasını söyler.
2. `swarm{action:"title", title:"..."}` ile sürüyü adlandırır.
3. Yalnız `supervisor` (`model:"gemini-4-hydrogen-high"`, `workspace:"inherit"`) eklenir; `hakem` başta eklenmez.
4. `supervisor`, görev haritasına göre `coder-*` (`gemini-4-hydrogen-medium`) ve tek `critic` (`gemini-4-hydrogen-xhigh`) ekler.
5. Ana sohbet turunu bitirir / `swarm_wait{since: N}` ile uyur; yalnızca `@coordinator` etiketlendiğinde uyanır.

## 3. Kota Tasarrufu ve Döngü Önleme Kuralları

1. **ASLA `@all` yazma:** Yalnız sıradaki tek ajana `@isim` yaz (`@coder-1`, `@critic`, `@supervisor`).
2. **Uyku ücretsizdir; `kill` kalıcıdır:** `waiting` durumundaki üye mesaj almadıkça 0 token harcar; ancak işi biten geçici paralel `coder-2..N` dalları `main`'e birleştirildikten sonra `swarm{action:"kill", name:"..."}` ile kapatılır. `hakem` bir kez açıldıysa tekrar gerekeceği faz kapısına kadar `waiting` bırakılır (`kill` yapılırsa yenisi `hakem-2` adını almak zorunda kalır).
3. **Argon disiplini ve kota yedeği:** `gemini-4-argon-high` haftalık kotalıdır; rutin görev onayı için asla uyandırılmaz. Argon kotası `%0` ise veya kullanıcı Argon'u yasakladıysa, `supervisor` (`gemini-4-hydrogen-high`) bizzat hakemlik yapar ya da kullanıcı onayıyla yedek modele geçer; kotası biten Argon tekrar denenmez.
4. **Kota tükenirse:** İşçiyi `kill` + `add` yapma; `swarm{action:"model", name:"...", model:"..."}` ile konuşma geçmişini koruyarak geçir ve kullanıcıya bildir.
5. **Ping-Pong ve 3 Deneme Freni:**
   - `coder` ↔ `critic` düzeltme turu görev başına en fazla **2 tur** sürer; 2. tur sonunda uyuşmazlık sürerse `supervisor` konuyu `@hakem`'e taşır.
   - `hakem` `ONAY` veya `GEREKSİZ` hükmü verdiyse `critic` aynı itirazı bir daha açamaz.
   - Aynı hata/test arızası en fazla **3 farklı hipotezle** denenir; çözülmezse görev `BLOCKED` olarak `BLOCKERS.md`'ye yazılıp bağımsız göreve geçilir.
6. **Kapsam kilidi ve `DUR`:** Planda olmayan fikirler `IDEAS.md`'ye tek satır düşülür. Final rapordan sonra kendiliğinden yeni işe başlanmaz.

## 4. Kısa İleti Şablonları

- **`supervisor → @coder-1`:** `Görevin <T-ID>. Yalnız <dosyalar> üzerinde çalış. TDD ile uygula, <proje doğrulama ve test komutları> çalıştır, commit at ve diff özeti + gerçek komut çıktısını @supervisor'a yaz.`
- **`supervisor → @critic`:** `<T-ID> commit <hash> ve diff'ini tasarım/testlere göre denetle. Yalnız @supervisor'a "ONAY" veya "RED + somut çözüm" yaz.`
- **`supervisor → @hakem` (yalnız uyuşmazlık/kapıda):** `critic <bulgu> diyor, coder <gerekçe> diyor. <hash/diff> ile tasarıma göre bu değişiklik gerçekten gerekli mi? @supervisor'a "ONAY / DÜZELT / GEREKSİZ" bildir.`
- **`supervisor → @coordinator`:** `[DURUM %XX | N/M] <Faz/görev özeti>. Açık engel: <yok veya kısa>. Sıradaki: <sonraki adım>.`

## 5. Kırmızı Çizgiler

| Tuzak | Doğrusu |
|---|---|
| Ana sohbetin `src/` veya uzun log okuması | Görevi `@supervisor`'a bırak, kendi context'ini temiz tut |
| `hakem` (`argon-high`) ajanını oturum başında açık tutmak | Yalnız uyuşmazlık, ağır itiraz veya büyük kapıda `add` et / uyandır |
| `critic` (`hydrogen-xhigh`) ajanının dosya düzenlemesi | `critic` yalnız eleştirir ve çözüm yolu yazar; `coder` düzeltir |
| `critic` ile `coder`'ın sonsuz ping-pong yapması | 2 turda bitmezse `@hakem` bağlayıcı hükmü verir, aynı itiraz tekrarlanmaz |
| `@all` ile tüm sürüyü uyandırmak | Her mesajda yalnız tek `@isim` kullan |
| Çalışmayan kodu "tamamlandı" raporlamak | Her onay gerçek test komut çıktısına ve diff'e dayanır |
