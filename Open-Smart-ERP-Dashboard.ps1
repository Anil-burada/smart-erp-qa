$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
  throw 'Missing Python environment. Install Smart ERP QA first with Install-Windows.bat.'
}
$uri = 'http://127.0.0.1:8766'
function Test-SmartErp {
  try {
    $response = Invoke-WebRequest -Uri "$uri/api/browser/status" -TimeoutSec 2 -UseBasicParsing
    return $response.StatusCode -eq 200
  } catch { return $false }
}
if (-not (Test-SmartErp)) {
  $args = '-NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $PSScriptRoot 'Start-Windows.ps1') + '"'
  Start-Process -FilePath 'powershell.exe' -ArgumentList $args -WorkingDirectory $PSScriptRoot
  $ready = $false
  for ($i=0; $i -lt 50; $i++) {
    if (Test-SmartErp) { $ready=$true; break }
    Start-Sleep -Milliseconds 500
  }
  if (-not $ready) { throw 'Smart ERP dashboard did not become ready. Check the Smart ERP server window for details (possibly port 8766 already in use).' }
}
Start-Process $uri
Write-Host 'Smart ERP dashboard opened in your browser.' -ForegroundColor Green
