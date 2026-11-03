# Start Smart ERP QA; do not run another copy if port 8766 is already in use.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Python environment not installed. Run Install-Windows.bat first.'
}
try {
    $listeners = @(Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue)
} catch { $listeners = @() }
if ($listeners.Count -gt 0) {
    $pidOnPort = $listeners[0].OwningProcess
    Write-Host "Port 8766 is already being used by process $pidOnPort." -ForegroundColor Yellow
    Write-Host 'Check http://127.0.0.1:8766 in your browser.'
    Write-Host 'If an older server is running, stop that server before starting a second copy.'
    exit 1
}
Write-Host 'Starting Smart ERP QA dashboard at http://127.0.0.1:8766 ...' -ForegroundColor Green
Write-Host 'Keep this window open while using the dashboard. Press Ctrl+C to stop.'
& $python 'run.py'
exit $LASTEXITCODE
