# Uygulama Notu: Google Chrome (M3)

## Önerilen Yöntem

1. **Web sayfası içi DOM işlemleri:** Sayfa içi form doldurma, bağlantı tıklama ve veri okuma işlerinde saf ekran pikseli yerine Chrome DevTools / Playwright MCP araçlarını tercih edin.
2. **İşletim sistemi düzeyindeki diyaloglar (Dosya Aç / Farklı Kaydet / Yazdır / İzin):** Tarayıcı DOM araçlarının erişemediği yerel Windows dosya seçme pencerelerinde `ui_elements(window="exe:chrome.exe")` veya `find_text(query="Kaydet", target="window:exe:chrome.exe")` kullanın.
3. **Adres çubuğu ve sekme kısayolları:** Görsel tıklama yerine `press_keys("ctrl+l")`, `press_keys("ctrl+t")`, `press_keys("ctrl+w")` kısayollarını kullanın.

## Bilinen Tuzak

- **Çoklu süreç (`chrome.exe`) ve gizli pencereler:** Chrome birden fazla arka plan süreci çalıştırır. `list_windows(query="exe:chrome.exe")` yalnızca görünür ve sahipsiz üst düzey pencereleri Z-sırasıyla döndürür; yine de birden fazla Chrome penceresi açıksa `warnings` listesini kontrol edin veya `hwnd:<id>` ile hedefleyin.
- **Büyük/küçük UIA ağacı:** Karmaşık bir web sayfasında erişilebilirlik ağacı binlerce düğüm içerebilir. EDM `collect_elements` çağrısını `max_elements=150` ve `5.0 s` zaman aşımıyla sınırlar (`truncated: true`).

## Doğrulama Durumu

- Birim testleri (`test_collect_elements_timeout_partial`, `test_select_prefers_topmost`): **PASS**.
- Kullanıcının masaüstünde gerçek Chrome yerel dosya diyaloğu üzerinde canlı M3 doğrulaması: **doğrulanacak**.
