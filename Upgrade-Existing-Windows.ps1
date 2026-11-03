# Smart ERP QA v6.1.9 - embedded ERP + workflow manager upgrade.
# Do NOT run from within the new extracted project to modify that same folder.
param([Parameter(Mandatory=$true)][string]$TargetPath)
$ErrorActionPreference = 'Stop'
$source = $PSScriptRoot
$target = (Resolve-Path -LiteralPath $TargetPath).Path
if ($source -eq $target) { throw 'Source and target are the same folder. Select your existing Smart ERP project.' }
foreach ($need in @('run.py','backend\api.py','frontend\app.js')) {
  if (-not (Test-Path -LiteralPath (Join-Path $target $need))) {
    throw "Wrong target folder: missing $need. Select the inner Smart ERP folder containing run.py."
  }
}
$inUse = Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue
if ($inUse) { throw 'Port 8766 is occupied. Stop the currently running Smart ERP server before applying this update.' }
$replace = @('backend\api.py','backend\workflow_manage.py','frontend\app.js','frontend\styles.css','backend\browser.py',
             'tests\test_workflow_manager_v618.py','tests\test_embedded_browser_v619.py','WORKFLOW_MANAGER_GUIDE.md','EMBEDDED_BROWSER_GUIDE.md')
$missing = @()
foreach ($file in (Get-ChildItem -LiteralPath (Join-Path $source 'backend') -Filter '*.py' -File)) {
  $relative = 'backend\' + $file.Name
  if (-not (Test-Path -LiteralPath (Join-Path $target $relative))) { $missing += $relative }
}
foreach ($relative in @($replace + $missing | Select-Object -Unique)) {
  if (-not (Test-Path -LiteralPath (Join-Path $source $relative))) { throw "Package is missing $relative" }
}
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backup = Join-Path $target ('backup_before_workflow_manager_' + $stamp)
foreach ($relative in @($replace + $missing | Select-Object -Unique)) {
  $old = Join-Path $target $relative
  if (Test-Path -LiteralPath $old) {
    $backupFile = Join-Path $backup $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $backupFile) -Force | Out-Null
    Copy-Item -LiteralPath $old -Destination $backupFile -Force
  }
}
foreach ($relative in @($replace + $missing | Select-Object -Unique)) {
  $new = Join-Path $target $relative
  New-Item -ItemType Directory -Path (Split-Path -Parent $new) -Force | Out-Null
  Copy-Item -LiteralPath (Join-Path $source $relative) -Destination $new -Force
  Write-Host "Updated $relative"
}
Write-Host ''
Write-Host 'Smart ERP QA v6.1.9 embedded ERP and workflow manager upgrade complete.' -ForegroundColor Green
Write-Host "Code backup: $backup"
Write-Host 'Existing project registry, workflows, locator JSON, .env, reports and executions were NOT changed.'
Write-Host 'Restart your OLD project with .\.venv\Scripts\python.exe run.py; refresh browser with Ctrl+Shift+R.'
