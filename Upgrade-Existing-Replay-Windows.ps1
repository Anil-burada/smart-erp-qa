param([Parameter(Mandatory=$true)][string]$TargetPath)
$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$target = (Resolve-Path -LiteralPath $TargetPath).Path
if ($source -eq $target) { throw 'Source and target folders are identical. No upgrade is required.' }
foreach ($required in @('run.py','frontend\app.js','backend\browser.py','Open-Smart-ERP-Web.bat')) {
  if (-not (Test-Path -LiteralPath (Join-Path $target $required))) {
    throw "Not a Smart ERP QA v6.2.3 project folder: missing $required"
  }
}
$listener = Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue
if ($listener) { throw 'Close Smart ERP web backend (port 8766) before upgrading; no files were changed.' }
$files = @('frontend\app.js','backend\browser.py','tests\test_replay_common_gate_v624.py','REPLAY_FIX_V624.md')
foreach ($file in $files) {
  if (-not (Test-Path -LiteralPath (Join-Path $source $file))) { throw "Upgrade ZIP is missing $file" }
}
$backup = Join-Path $target ('backup_before_replay_v624_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
foreach ($file in $files) {
  $destination = Join-Path $target $file
  if (Test-Path -LiteralPath $destination) {
    $prior = Join-Path $backup $file
    New-Item -ItemType Directory -Path (Split-Path -Parent $prior) -Force | Out-Null
    Copy-Item -LiteralPath $destination -Destination $prior -Force
  }
  New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
  Copy-Item -LiteralPath (Join-Path $source $file) -Destination $destination -Force
  Write-Host "Updated: $file"
}
Write-Host 'Smart ERP Replay v6.2.4 installed. All projects, workflows, locator JSON, .env, SQLite and reports were preserved.' -ForegroundColor Green
Write-Host "Code backup: $backup"
Write-Host 'Start Open-Smart-ERP-Web.bat and open http://127.0.0.1:8766 in Chrome.'
