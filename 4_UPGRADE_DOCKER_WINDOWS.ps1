$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
Write-Host 'Stopping Smart ERP and backing up data before rebuild...' -ForegroundColor Cyan
docker compose down
if ($LASTEXITCODE -ne 0) { throw 'Stop failed' }
& (Join-Path $PSScriptRoot '3_BACKUP_DOCKER_DATA_WINDOWS.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Backup failed; not upgrading.' }
& (Join-Path $PSScriptRoot '1_START_DOCKER_WINDOWS.ps1')
