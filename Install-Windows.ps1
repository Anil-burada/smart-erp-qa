# Smart ERP QA v6.3.0 - first-time Windows setup.
# Run from a downloaded/extracted project folder (not directly from inside a ZIP).
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
Write-Host 'Smart ERP QA - Installing on this laptop' -ForegroundColor Cyan

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv '.venv'
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv '.venv'
    } else {
        throw 'Python 3 is not installed. Install Python 3.11 or newer for Windows, then run Install-Windows.bat again.'
    }
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python virtual environment.' }
}
if (-not (Test-Path -LiteralPath $python)) { throw 'Python executable missing inside .venv.' }
& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed.' }
& $python -m pip install -r 'requirements.txt'
if ($LASTEXITCODE -ne 0) { throw 'Installing Python requirements failed.' }
& $python -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw 'Installing Chromium for Playwright failed.' }
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
    Write-Host 'Created .env from template. Update credentials locally when needed.' -ForegroundColor Yellow
} else {
    Write-Host 'Preserved existing .env.'
}
# Only a fresh installation gets mock ERP demo data. Never seed or alter
# an existing local project database during an upgrade.
if (-not (Test-Path -LiteralPath 'data\erpqa.sqlite3')) {
    Write-Host 'Initializing the harmless local mock ERP demo...' -ForegroundColor Cyan
    & $python 'scripts\seed_mock_demo.py'
    if ($LASTEXITCODE -ne 0) { throw 'Mock demo initialization failed; installation cannot be verified.' }
}
Write-Host ''
Write-Host 'SETUP COMPLETE. Double-click Start-Windows.bat to launch the dashboard.' -ForegroundColor Green
Write-Host 'Dashboard: http://127.0.0.1:8766 (local laptop only)'
