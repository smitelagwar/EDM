$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

Remove-Item Env:EDM_FAKE -ErrorAction SilentlyContinue

Write-Host "==> Checking desktop session via edm doctor..."
$doctorRaw = uv run edm doctor
if ($LASTEXITCODE -ne 0) {
    Write-Error "edm doctor komutu başarısız oldu (çıkış kodu: $LASTEXITCODE)."
    exit $LASTEXITCODE
}

$doctor = $doctorRaw | ConvertFrom-Json
$state = $doctor.session.state
if ($state -ne "ok") {
    Write-Host "HATA: Etkileşimli masaüstünde (WinSta0\Default) değilsiniz (session.state = '$state')." -ForegroundColor Red
    Write-Host "Lütfen bu betiği kendi Windows kullanıcı oturumunuzdaki bir PowerShell penceresinde çalıştırın." -ForegroundColor Yellow
    exit 3
}

Write-Host "==> Running live acceptance test suite (L1-L12)..."
$dateStr = Get-Date -Format "yyyy-MM-dd"
$reportDir = Join-Path $RepoRoot "docs\acceptance"
if (-not (Test-Path $reportDir)) {
    New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
}
$reportPath = Join-Path $reportDir "live-$dateStr.md"

$pytestOut = uv run pytest -m live --timeout=120 -p no:cacheprovider -v 2>&1 | Out-String
$pytestCode = $LASTEXITCODE

$reportContent = @"
# EDM Canlı Kabul Raporu ($dateStr)

- **Durum:** $(if ($pytestCode -eq 0) { "PASS" } else { "FAIL (exit=$pytestCode)" })
- **Oturum:** $($doctor.session.station)\$($doctor.session.thread_desktop) (state=$($doctor.session.state))
- **İnşa / Python:** Windows $($doctor.os_build) / Python $($doctor.python)
- **DPI Farkındalığı:** $($doctor.dpi_awareness)

## Pytest Çıktısı (Metin Özeti — Ekran Görüntüsü İçermez)

````text
$($pytestOut.Trim())
````
"@

Set-Content -Path $reportPath -Value $reportContent -Encoding UTF8
Write-Host "==> Canlı kabul raporu yazıldı: $reportPath"
exit $pytestCode
