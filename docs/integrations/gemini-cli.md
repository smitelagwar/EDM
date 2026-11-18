# Gemini CLI Entegrasyonu (`edm`)

## 1. Kurulum

```powershell
uv tool install --editable C:\Users\hsyn\Desktop\EDM
```

## 2. `~/.gemini/settings.json` Yapılandırması

`C:\Users\<kullanıcı>\.gemini\settings.json` dosyasındaki `mcpServers` nesnesine `edm` girdisini ekleyin:

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

*(Not: Gemini CLI sürümünüzde ek `trust` veya `timeout` alanları gerekiyorsa resmî Gemini CLI MCP belgesinden doğrulanmalıdır — doğrulanacak.)*
