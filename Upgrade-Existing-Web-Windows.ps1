param([Parameter(Mandatory=$true)][string]$TargetPath)
$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$target = (Resolve-Path -LiteralPath $TargetPath).Path
if ($source -eq $target) { throw 'Source and target are identical. You already have the new project.' }
foreach ($needed in @('run.py','frontend\index.html','backend\api.py')) {
  if (-not (Test-Path -LiteralPath (Join-Path $target $needed))) { throw "Not a Smart ERP QA root: missing $needed" }
}
$port = Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue
if ($port) { throw 'Stop the old backend on port 8766 before upgrading. No files changed.' }
$files = @('frontend\app.js','frontend\index.html','frontend\styles.css',
           'Open-Smart-ERP-Web.ps1','Open-Smart-ERP-Web.bat','WEB_DASHBOARD_GUIDE.md')
$backup = Join-Path $target ('backup_before_web_v623_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
foreach ($file in $files) {
  $from = Join-Path $source $file
  if (-not (Test-Path -LiteralPath $from)) { throw "Missing source file: $file" }
}
foreach ($file in $files) {
  $to = Join-Path $target $file
  if (Test-Path -LiteralPath $to) {
    $previous = Join-Path $backup $file
    New-Item -ItemType Directory -Path (Split-Path $previous -Parent) -Force | Out-Null
    Copy-Item -LiteralPath $to -Destination $previous -Force
  }
  New-Item -ItemType Directory -Path (Split-Path $to -Parent) -Force | Out-Null
  Copy-Item -LiteralPath (Join-Path $source $file) -Destination $to -Force
  Write-Host "Updated: $file"
}
Write-Host 'Web dashboard update installed. Projects, workflows, .env, data and SQLite were not changed.' -ForegroundColor Green
Write-Host "Backups: $backup"
Write-Host 'Double-click Open-Smart-ERP-Web.bat, then use http://127.0.0.1:8766 in Chrome.'
