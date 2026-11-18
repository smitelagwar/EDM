# Uygulama Notu: AOC G-Menu ve Yönetici Yetkili Araçlar (M4, M5)

## Önerilen Yöntem

1. **UIPI (User Interface Privilege Isolation) tespiti:** AOC G-Menu, Görev Yöneticisi veya donanım kontrol yazılımları genellikle yüksek bütünlük düzeyinde (`Integrity.high` — Administrator) çalışır.
2. Normal (`Integrity.medium`) bir EDM sürecinden bu pencerelere `click`, `type_text` veya `window_action` gönderildiğinde EDM `guard.preflight` aşamasında hedef sürecin bütünlük düzeyini kontrol eder ve `ELEVATION_REQUIRED` (`retryable: false`) döndürür.
3. **Çözüm yolu:** Bu hatayı aldığınızda tekrar denemeyin. Kullanıcıya EDM'yi (veya bağlı MCP sunucusunu / `edm serve-http` oturumunu) **Yönetici olarak (Run as Administrator)** başlatması gerektiğini bildirin.

## Bilinen Tuzak

- **Sessiz `SendInput` kaybı:** Windows çekirdeği, `medium` bütünlükteki bir süreçten `high` bütünlükteki pencereye gönderilen `SendInput` veya `WM_CLOSE` mesajlarını güvenlik nedeniyle reddeder. EDM'nin `process_integrity` + `SendInput` dönüş sayısı kontrolü sessiz no-op'u engelleyip açık hata üretir.
- **UAC istemi (`SECURE_DESKTOP` — M5):** Yönetici onayı penceresi açıldığında masaüstü `Winlogon` güvenli masaüstüne geçer. EDM asılı kalmadan `SECURE_DESKTOP` döndürür; kullanıcı onayladıktan sonra `wait_for("stable")` ile devam edilir.

## Doğrulama Durumu

- Birim testleri (`test_preflight_elevation_required`, `test_preflight_unknown_integrity_assumed_elevated`, `test_preflight_secure_desktop`, `test_window_action_guard_and_uipi`): **PASS**.
- Kullanıcının masaüstünde gerçek AOC G-Menu / UAC üzerinde canlı M4/M5 doğrulaması: **doğrulanacak**.
