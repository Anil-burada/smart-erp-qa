$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Install Docker Desktop and enable WSL 2 first.' }
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop is not running. Open it, then rerun this script.' }
docker compose version
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose plugin is missing.' }
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
Write-Host 'Building and starting Smart ERP QA (localhost only)...' -ForegroundColor Cyan
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose startup failed. Run docker compose logs smart-erp.' }
Write-Host 'Dashboard: http://127.0.0.1:8766' -ForegroundColor Green
Write-Host 'Login manually in the managed ERP viewer before replay. Browser lives INSIDE Docker.'
