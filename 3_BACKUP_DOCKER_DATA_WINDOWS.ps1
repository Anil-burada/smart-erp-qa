$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (Get-Command docker -ErrorAction SilentlyContinue) {
  $running = docker compose ps --status running --services 2>$null
  if ($running -contains 'smart-erp') { throw 'Stop Docker first with .\2_STOP_DOCKER_WINDOWS.ps1 before backing up SQLite.' }
}
$backupRoot = Join-Path $PSScriptRoot 'backups'
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$zip = Join-Path $backupRoot ("SmartERP_Data_$stamp.zip")
$files = @('data','projects','workflows','approval_plans','artifacts','reports','uploaded_scripts') | Where-Object { Test-Path (Join-Path $PSScriptRoot $_) }
if (-not $files) { throw 'No Smart ERP data folders found to back up.' }
Compress-Archive -Path $files -DestinationPath $zip -CompressionLevel Optimal
Write-Host "Backup: $zip" -ForegroundColor Green
Write-Host 'Keep this archive private; it may contain ERP URLs and screenshot evidence.'
