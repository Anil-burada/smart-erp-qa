# Smart ERP QA v6.2.7. Only replaces selected source and documentation files.
# Requires a stopped web backend. Backs up existing code before changing any file.
param([Parameter(Mandatory=$true)][string]$TargetPath)
$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$target = (Resolve-Path -LiteralPath $TargetPath).Path
if ($source -eq $target) { throw 'The source and target are identical; open the existing dashboard directly.' }
foreach ($required in @('run.py','backend\api.py','backend\browser.py','frontend\app.js','Open-Smart-ERP-Web.bat')) {
  if (-not (Test-Path -LiteralPath (Join-Path $target $required))) {
    throw "Not a Smart ERP project folder. Missing $required. No files changed."
  }
}
$files = @(
  'backend\api.py',
  'backend\browser.py',
  'backend\session_replay.py',
  'frontend\app.js',
  'frontend\styles.css',
  'tests\test_existing_session_v627.py',
  'tests\test_workflow_manager_v618.py',
  'REPLAY_EXISTING_SESSION_GUIDE_V627.md',
  'V6_CHANGELOG.md',
  'README.md'
)
foreach ($item in $files) {
  if (-not (Test-Path -LiteralPath (Join-Path $source $item))) {
    throw "Incomplete upgrade ZIP. Missing $item. No files changed."
  }
}
$listener = @(Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue)
if ($listener.Count -gt 0) {
  foreach ($conn in $listener) {
    $ownerPID = $conn.OwningProcess
    $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$ownerPID" -ErrorAction SilentlyContinue
    Write-Warning "Port 8766 is occupied by PID $ownerPID ($($owner.Name))."
  }
  throw 'Stop the Smart ERP server terminal using Ctrl+C, verify port 8766 is free, then rerun this upgrade. No files were changed.'
}
$backup = Join-Path $target ('backup_before_existing_session_v627_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
$existing = @{}
# Back up all replacement files before modifying anything.
foreach ($item in $files) {
  $dest = Join-Path $target $item
  $present = Test-Path -LiteralPath $dest
  $existing[$item] = $present
  if ($present) {
    $saved = Join-Path $backup $item
    New-Item -ItemType Directory -Path (Split-Path -Parent $saved) -Force | Out-Null
    Copy-Item -LiteralPath $dest -Destination $saved -Force
  }
}
$written = New-Object System.Collections.ArrayList
try {
  foreach ($item in $files) {
    $dest = Join-Path $target $item
    New-Item -ItemType Directory -Path (Split-Path -Parent $dest) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $source $item) -Destination $dest -Force
    [void]$written.Add($item)
    Write-Host "Updated $item"
  }
} catch {
  foreach ($item in $written) {
    $dest = Join-Path $target $item
    if ($existing[$item]) {
      Copy-Item -LiteralPath (Join-Path $backup $item) -Destination $dest -Force
    } else {
      Remove-Item -LiteralPath $dest -Force -ErrorAction SilentlyContinue
    }
  }
  throw 'Upgrade failed; previously changed files were restored from the code backup. Check permissions and retry.'
}
Write-Host 'Smart ERP QA v6.2.7 current-session replay + Yes/No removal installed.' -ForegroundColor Green
Write-Host "Code backup: $backup"
Write-Host 'Preserved: .env, projects, workflows, data/SQLite, login selectors, approval plans, business flows and reports.'
Write-Host 'Start Open-Smart-ERP-Web.bat and visit http://127.0.0.1:8766.'
