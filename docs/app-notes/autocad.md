# Uygulama Notu: AutoCAD (M1, M8)

## Önerilen Yöntem

1. **Komut satırı ve kısayollar önce gelir:** Çizim ve düzenleme komutlarını ribbon üzerinde piksel aramak yerine doğrudan klavye ile (`type_text("LINE\n")`, `press_keys("esc")`) gönderin.
2. **Küçük ribbon ve durum çubuğu ikonları:** Tam ekran `screenshot` üzerinde doğrudan tıklamak yerine önce ilgili şeridi `zoom(observation_id=..., x=..., y=..., w=..., h=...)` ile 2×–4× büyütün, ardından dönen alt gözlem üzerinden `click` çağırın.
3. **Sürekli çizim ve 3B görünüm / pan (M8):**
   - Çok noktalı polyline veya serbest eskiz için `draw_path(observation_id=..., points=[[x1,y1], ...], smooth=False)` kullanın (kesintisiz `WM_MOUSEMOVE` ürettiği için AutoCAD OSNAP izlemesi çalışır).
   - Orta tuş pan veya `Shift + Orta Tuş` 3B orbit için `key_state("shift", "down")` + `drag(..., button="middle")` + `key_state("shift", "up")` veya `run_sequence` kullanın.

## Bilinen Tuzak

- **DirectX görünüm alanı UIA'ya kapalıdır:** Çizim alanı içindeki geometrik nesneler `ui_elements` içinde görünmez; yalnızca üst şerit, durum çubuğu ve standart modal diyaloglar UIA ile okunabilir.
- **Örtülü pencerede boş kare:** Donanım hızlandırmalı görünüm alanı `PrintWindow` altında siyah/boş dönebilir. EDM'nin `is_blank` kontrolü ve görünür pencerede GDI (`mss`), örtülü pencerede WGC (`windows-capture`) sırası bu tuzağı önler.
- **Modal diyalog / komut istemi kilidi:** Açık bir modal pencere (`GetLastActivePopup`) varken ana pencereye yapılan tıklamalar `STALE_OBSERVATION` ile reddedilir; önce yeni `screenshot` alınmalıdır.

## Doğrulama Durumu

- Birim testleri (`test_capturer_falls_back_on_blank`, `test_draw_path_continuous_and_releases_on_abort`, `test_zoom_maps_back`): **PASS**.
- Kullanıcının masaüstünde gerçek AutoCAD oturumu üzerinde canlı M1/M8 doğrulaması: **doğrulanacak**.
