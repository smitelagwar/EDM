# Claude Code Entegrasyonu (`edm`)

## 1. Kurulum

```powershell
uv tool install --editable C:\Users\hsyn\Desktop\EDM
```

## 2. MCP Sunucusunu Ekleme

Claude Code CLI üzerinden kullanıcı kapsamına (`--scope user`) `edm` MCP sunucusunu kaydedin:

```powershell
claude mcp add --scope user edm -- edm mcp
```

Kaydı doğrulamak için:

```powershell
claude mcp list
```

İlk oturumda Claude'dan `edm` `doctor` aracını çağırmasını isteyerek `session.state == "ok"` olduğunu doğrulayın.
