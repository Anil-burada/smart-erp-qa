$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
docker compose down
if ($LASTEXITCODE -ne 0) { throw 'Docker compose down failed' }
Write-Host 'Stopped. Project and test data were retained.' -ForegroundColor Green
