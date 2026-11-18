# Antigravity İstemci Entegrasyonu (`edm`)

## 1. Kurulum

Kendi etkileşimli Windows PowerShell oturumunuzda EDM aracını `uv tool` ile kurun:

```powershell
uv tool install --editable C:\Users\hsyn\Desktop\EDM
edm --version
```

## 2. MCP Sunucusu Kaydı (`stdio`)

Antigravity MCP yapılandırma dosyası (`~/.gemini/config/mcp_config.json`) içine `edm` girdisini ekleyin:

```json
{
  "mcpServers": {
    "edm": {
      "command": "edm",
      "args": ["mcp"]
    }
  }
}
```

## 3. İlk Doğrulama ve İzole Masaüstü (`WinSta0\exebox-...`) Köprüsü

1. Kayıttan sonra Antigravity sohbetinde ajana bir kez `doctor` aracını çağırtın.
2. Dönüşte `session.state == "ok"` ise `stdio` bağlantısı doğrudan kullanıcının etkileşimli (`WinSta0\Default`) masaüstünde çalışmaktadır; ek işlem gerekmez.
3. Eğer Antigravity alt süreci `WinSta0\exebox-...` izole masaüstünde başlatırsa `doctor` çıktısı `session.state == "isolated_desktop"` döndürür. Bu durumda:
   - **Kullanıcı olarak kendi etkileşimli PowerShell pencerenizde** loopback HTTP sunucusunu başlatın:
     ```powershell
     edm serve-http --host 127.0.0.1 --port 8765
     ```
   - İlk çalıştırmada `%APPDATA%\EDM\http-token` dosyasında 32 baytlık bir Bearer belirteci üretilir ve ekrana basılır.
   - `mcp_config.json` içinde `url` ve `headers` (Antigravity sürümünüzün HTTP MCP başlık desteğine göre — *doğrulanacak*) şu şekilde tanımlanır:
     ```json
     {
       "mcpServers": {
         "edm": {
           "url": "http://127.0.0.1:8765/mcp",
           "headers": {
             "Authorization": "Bearer <HTTP_TOKEN>"
           }
         }
       }
     }
     ```
   - İstemci sürümü özel `headers` alanını desteklemiyorsa bu sınır bilinmeli ve `edm` CLI/MCP doğrudan etkileşimli masaüstü oturumunda çalıştırılmalıdır.

## 4. `edm snip` İçin Windows Kısayol Tuşu Atama

1. Masaüstünde sağ tıklayın → **Yeni → Kısayol**.
2. Konum olarak `edm.exe snip` (veya `%USERPROFILE%\.local\bin\edm.exe snip`) girin ve kısayolu `EDM Snip.lnk` adıyla kaydedin.
3. Kısayola sağ tıklayın → **Özellikler → Kısayol** sekmesi → **Kısayol tuşu** alanına örneğin `Ctrl + Alt + S` basın ve **Tamam**'a tıklayın.
4. Artık istediğiniz anda kısayola basarak ekranda bölge seçebilir ve ajana `get_user_snips` ile inceletebilirsiniz.
