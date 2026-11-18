# Codex Desktop / CLI Entegrasyonu (`edm`)

## 1. Kurulum

```powershell
uv tool install --editable C:\Users\hsyn\Desktop\EDM
edm doctor
```

## 2. `~/.codex/config.toml` Yapılandırması

`C:\Users\<kullanıcı>\.codex\config.toml` dosyasına aşağıdaki bölümü ekleyin:

```toml
[mcp_servers.edm]
command = "edm"
args = ["mcp"]
```

*(Not: Codex CLI/Desktop sürümünüze göre `[mcp_servers.edm]` anahtar adı resmî Codex MCP belgesinden doğrulanmalıdır — doğrulanacak.)*

## 3. Ajan Becerisi (`SKILL.md`)

`integrations/skills/edm-desktop/SKILL.md` klasörünü `~/.codex/skills/edm-desktop/SKILL.md` altına kopyalayarak veya sembolik bağ oluşturarak ajanınızın EDM strateji merdivenini otomatik izlemesini sağlayabilirsiniz.
