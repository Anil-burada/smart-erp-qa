# Smart ERP QA v6.2.5 code-only upgrade. No project/data/database modification.
param([Parameter(Mandatory=$true)][string]$TargetPath)
$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$target = (Resolve-Path -LiteralPath $TargetPath).Path
if ($source -eq $target) { throw 'Source and target are the same folder; use Open-Smart-ERP-Web.bat directly.' }
foreach ($required in @('run.py','backend\api.py','backend\browser.py','frontend\app.js','Open-Smart-ERP-Web.bat')) {
  if (-not (Test-Path -LiteralPath (Join-Path $target $required))) {
    throw "Wrong Smart ERP QA project folder. Missing $required"
  }
}
$listener = Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue
if ($listener) { throw 'Stop the Smart ERP FastAPI server on port 8766 before installing. No files were changed.' }
$files = @(
  'backend\api.py', 'backend\browser.py', 'backend\nav_recovery.py',
  'frontend\app.js', 'frontend\index.html',
  'tests\test_login_navigation_v625.py', 'LOGIN_REPLAY_GUIDE_V625.md', 'V6_CHANGELOG.md',
  'Stop-Smart-ERP-Web.ps1'
)
foreach ($file in $files) {
  if (-not (Test-Path -LiteralPath (Join-Path $source $file))) {
    throw "Upgrade package is missing $file; no files were changed."
  }
}
$backup = Join-Path $target ('backup_before_login_replay_v625_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
foreach ($file in $files) {
  $destination = Join-Path $target $file
  if (Test-Path -LiteralPath $destination) {
    $saved = Join-Path $backup $file
    New-Item -ItemType Directory -Path (Split-Path -Parent $saved) -Force | Out-Null
    Copy-Item -LiteralPath $destination -Destination $saved -Force
  }
  New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
  Copy-Item -LiteralPath (Join-Path $source $file) -Destination $destination -Force
  Write-Host "Updated: $file"
}
Write-Host 'Smart ERP QA v6.2.5 LOGIN + REPLAY update installed.' -ForegroundColor Green
Write-Host "Code backup: $backup"
Write-Host 'Untouched: ERP projects, saved workflow JSON, locator JSON, login.json, .env, SQLite database, reports and recordings.'
Write-Host 'Open the dashboard using Open-Smart-ERP-Web.bat and http://127.0.0.1:8766. Press Ctrl+Shift+R.'
