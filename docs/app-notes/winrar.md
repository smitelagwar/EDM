# Uygulama Notu: WinRAR (M2)

## Önerilen Yöntem

1. **Toplu arşivleme ve açma işlemlerinde CLI önce gelir:** GUI penceresi açıp düğme tıklamak yerine doğrudan `rar.exe` veya `unrar.exe` komut satırı aracını kullanın.
2. **GUI diyalogları (şifre, üzerine yazma, arşiv seçenekleri):** WinRAR standart Win32 pencere kontrolleri kullandığından `ui_elements(window="exe:WinRAR.exe")` çağrısıyla tüm düğme (`Button`), onay kutusu (`CheckBox`) ve metin alanları (`Edit`) yüksek doğrulukla numaralandırılır. Tıklama için `click(observation_id=..., mark=N)` kullanın.

## Bilinen Tuzak

- **Arka planda açılan onay pencereleri:** Üzerine yazma veya parola istemi yeni bir modal popup açtığında eski gözlem `GetLastActivePopup` kontrolüyle `STALE_OBSERVATION` döndürür. Bu durumda yeni `ui_elements` veya `screenshot` alınmalıdır.
- **Türkçe karakterli dosya adları:** Arama veya filtreleme yaparken `find_text` (`tr_fold` destekli) veya doğrudan `type_text` (`KEYEVENTF_UNICODE`) kullanın.

## Doğrulama Durumu

- Birim testleri (`test_filter_and_order`, `test_click_by_mark_resolves_center`): **PASS**.
- Kullanıcının masaüstünde gerçek WinRAR uygulaması üzerinde canlı M2 doğrulaması: **doğrulanacak**.
