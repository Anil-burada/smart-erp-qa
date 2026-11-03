# Start the existing local FastAPI dashboard without Electron/Node or another ERP window.
# Run once per Windows login; afterward use http://127.0.0.1:8766 in Chrome.
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Set-Location -LiteralPath $root
$python = Join-Path $root '.venv\Scripts\python.exe'
$url = 'http://127.0.0.1:8766'
if (-not (Test-Path -LiteralPath $python)) { throw 'Python environment missing. Run Install-Windows.bat from this folder first.' }
function Test-Dashboard {
  try {
    $response = Invoke-WebRequest -Uri "$url/api/health" -UseBasicParsing -TimeoutSec 2
    return $response.StatusCode -eq 200
  } catch { return $false }
}
if (-not (Test-Dashboard)) {
  $listener = Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue
  if ($listener) { throw 'Port 8766 is occupied by a process that is not responding as Smart ERP. Stop the old server before retrying.' }
  $logs = Join-Path $root 'logs'
  New-Item -ItemType Directory -Path $logs -Force | Out-Null
  $out = Join-Path $logs 'web_backend_stdout.log'
  $err = Join-Path $logs 'web_backend_stderr.log'
  # Force WEB mode, never attempt to connect to an Electron CDP browser.
  $env:SMART_ERP_DESKTOP = '0'
  $process = Start-Process -FilePath $python -ArgumentList @('run.py') -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
  $ready = $false
  for ($i=0; $i -lt 75; $i++) {
    if (Test-Dashboard) { $ready=$true; break }
    $process.Refresh()
    if ($process.HasExited) { break }
    Start-Sleep -Milliseconds 400
  }
  if (-not $ready) {
    Write-Host 'FastAPI could not start. Read logs\web_backend_stderr.log for the Python error.' -ForegroundColor Red
    if (Test-Path $err) { Get-Content $err -Tail 18 }
    throw 'Smart ERP web dashboard did not start. Your existing data was not changed.'
  }
}
Start-Process $url
Write-Host "Smart ERP QA opened at $url" -ForegroundColor Green
Write-Host 'Bookmark the URL in Chrome. The local backend must remain running for the link to work.'
