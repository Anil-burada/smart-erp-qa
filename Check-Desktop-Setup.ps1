# READ-ONLY diagnostics. Does not remove workflows, accounts or databases.
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
if (Test-Path 'C:\Program Files\nodejs\node.exe') {$env:Path = 'C:\Program Files\nodejs;' + $env:Path}
Write-Host 'SMART ERP QA Desktop Diagnostics' -ForegroundColor Cyan
Write-Host "Project: $root"
Write-Host "run.py exists: $(Test-Path (Join-Path $root 'run.py'))"
Write-Host "Python exists: $(Test-Path (Join-Path $root '.venv\Scripts\python.exe'))"
Write-Host "Electron installed: $(Test-Path (Join-Path $root 'desktop\node_modules\electron'))"
Write-Host '--- Node and npm ---'
node --version
npm.cmd --version
Write-Host '--- Listeners ---'
foreach($port in @(8766,9337)) {
  $listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  if ($listeners) { Write-Host "Port $port is LISTENING, PID $($listeners[0].OwningProcess)" }
  else { Write-Host "Port $port is NOT listening" }
}
Write-Host '--- Backend health ---'
try {Invoke-RestMethod 'http://127.0.0.1:8766/api/health' -TimeoutSec 3 | Format-List}
catch {Write-Host "Health endpoint not available: $($_.Exception.Message)"}
Write-Host '--- Recent backend errors ---'
$err = Join-Path $root 'logs\desktop_backend.stderr.log'
if (Test-Path $err) {Get-Content $err -Tail 25} else {Write-Host 'No desktop backend log yet. Start with Start-Desktop-Windows.bat.'}
