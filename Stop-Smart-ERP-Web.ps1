# Stop Smart ERP QA only after checking both FastAPI's identity and the Python command line.
# Supports a Windows venv whose executable resolves to a system Python path.
param([string]$TargetPath=$PSScriptRoot)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $TargetPath).Path
$connections = @(Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue)
if (-not $connections.Count) {
  Write-Host 'Port 8766 is free. Nothing to stop.' -ForegroundColor Green
  exit 0
}
try {
  $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8766/api/health' -TimeoutSec 3
} catch {
  throw 'Port 8766 is occupied, but its health endpoint is not Smart ERP. Refusing to stop the process.'
}
if ($health.ok -ne $true -or $health.mode -ne 'LOCAL_PLAYWRIGHT') {
  throw 'Port 8766 is not identified as Smart ERP QA. Nothing was stopped.'
}
foreach ($conn in $connections) {
  $procId = [int]$conn.OwningProcess
  $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue
  if (-not $proc) { continue }
  $cmd = [string]$proc.CommandLine
  if (($proc.Name -match '^python(w)?\.exe$') -and ($cmd -match '(?i)(^|\s|["\\])run\.py\b|backend\.api:app')) {
    Write-Host "Stopping verified Smart ERP backend PID $procId" -ForegroundColor Yellow
    Stop-Process -Id $procId -Force
  } else {
    Write-Warning "Refusing to stop PID $procId ($($proc.Name)); command line is not verified as Smart ERP."
    Write-Host "Command: $cmd"
  }
}
Start-Sleep -Milliseconds 800
if (Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue) {
  throw 'Port 8766 is still occupied. Close the original backend terminal with Ctrl+C after identifying its process.'
}
Write-Host 'Smart ERP stopped. Your project files were not changed.' -ForegroundColor Green
