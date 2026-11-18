param(
    [switch]$WriteConfig
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

Write-Host "==> Checking uv installation..."
$uvCmd = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvCmd) {
    throw "uv is not installed or not on PATH. Install uv from https://docs.astral.sh/uv/ first."
}

Write-Host "==> Installing edm-desktop via uv tool install --editable..."
uv tool install --editable $RepoRoot

Write-Host "==> Running edm doctor..."
edm doctor

Write-Host ""
Write-Host "================ MCP Client Configuration Snippets ================"
Write-Host "[Antigravity] ~/.gemini/config/mcp_config.json or [Gemini CLI] ~/.gemini/settings.json:"
Write-Host '{"mcpServers":{"edm":{"command":"edm","args":["mcp"]}}}'
Write-Host ""
Write-Host "[Codex] ~/.codex/config.toml:"
Write-Host "[mcp_servers.edm]`ncommand = `"edm`"`nargs = [`"mcp`"]"
Write-Host ""
Write-Host "[Claude Code] Run in terminal:"
Write-Host "claude mcp add --scope user edm -- edm mcp"
Write-Host "==================================================================="

if ($WriteConfig) {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $agPath = Join-Path $HOME ".gemini\config\mcp_config.json"
    $agDir = Split-Path -Parent $agPath
    if (-not (Test-Path $agDir)) {
        New-Item -ItemType Directory -Path $agDir -Force | Out-Null
    }
    if (Test-Path $agPath) {
        Copy-Item -Path $agPath -Destination "$agPath.bak-$timestamp" -Force
        $cfgObj = Get-Content -Path $agPath -Raw -Encoding UTF8 | ConvertFrom-Json
    } else {
        $cfgObj = [PSCustomObject]@{}
    }
    if (-not ($cfgObj.PSObject.Properties.Name -contains "mcpServers")) {
        $cfgObj | Add-Member -MemberType NoteProperty -Name "mcpServers" -Value ([PSCustomObject]@{})
    }
    $edmEntry = [PSCustomObject]@{
        command = "edm"
        args    = @("mcp")
    }
    $cfgObj.mcpServers | Add-Member -MemberType NoteProperty -Name "edm" -Value $edmEntry -Force
    $jsonText = $cfgObj | ConvertTo-Json -Depth 10
    Set-Content -Path $agPath -Value $jsonText -Encoding UTF8
    Write-Host "Updated $agPath (backup suffix: .bak-$timestamp)"
}
