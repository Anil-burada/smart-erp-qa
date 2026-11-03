# Smart ERP QA v6.2.6: update only code and guide; preserve all user data.
param([Parameter(Mandatory=$true)][string]$TargetPath)
$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$target = (Resolve-Path -LiteralPath $TargetPath).Path
if ($source -eq $target) { throw 'Source and target are the same folder. Run Open-Smart-ERP-Web.bat directly.' }
foreach ($required in @('run.py','backend\api.py','backend\browser.py','frontend\app.js','Open-Smart-ERP-Web.bat')) {
  if (-not (Test-Path -LiteralPath (Join-Path $target $required))) {
    throw "Wrong Smart ERP project folder. Missing $required"
  }
}
$listener = @(Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue)
if ($listener.Count -gt 0) {
  foreach ($conn in $listener) {
    $pidValue = $conn.OwningProcess
    $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$pidValue" -ErrorAction SilentlyContinue
    Write-Warning "Port 8766 is running as PID $pidValue ($($owner.Name))."
    if ($owner) { Write-Host "Executable: $($owner.ExecutablePath)" }
  }
  throw 'Close the Smart ERP backend terminal using Ctrl+C, and rerun the installer. No files were changed.'
}
$files = @(
  'backend\api.py',
  'backend\browser.py',
  'backend\login_discovery.py',
  'frontend\app.js',
  'tests\test_login_wizard_v626.py',
  'LOGIN_WIZARD_GUIDE_V626.md',
  'V6_CHANGELOG.md'
)
foreach ($item in $files) {
  if (-not (Test-Path -LiteralPath (Join-Path $source $item))) {
    throw "Upgrade package is incomplete. Missing $item. No files were changed."
  }
}
$backup = Join-Path $target ('backup_before_login_wizard_v626_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
foreach ($item in $files) {
  $dest = Join-Path $target $item
  if (Test-Path -LiteralPath $dest) {
    $saved = Join-Path $backup $item
    New-Item -ItemType Directory -Path (Split-Path -Parent $saved) -Force | Out-Null
    Copy-Item -LiteralPath $dest -Destination $saved -Force
  }
  New-Item -ItemType Directory -Path (Split-Path -Parent $dest) -Force | Out-Null
  Copy-Item -LiteralPath (Join-Path $source $item) -Destination $dest -Force
  Write-Host "Updated: $item"
}
Write-Host 'Smart ERP QA v6.2.6 Guided Login Wizard installed.' -ForegroundColor Green
Write-Host "Code backup: $backup"
Write-Host 'Preserved: .env, projects, workflows, data, SQLite, existing login.json and reports.'
Write-Host 'Launch Open-Smart-ERP-Web.bat and open http://127.0.0.1:8766 in Chrome.'
