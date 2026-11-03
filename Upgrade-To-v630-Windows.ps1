param([Parameter(Mandatory=$true)][string]$TargetPath)
$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$target = (Resolve-Path -LiteralPath $TargetPath).Path
if ($source -eq $target) { throw 'Extract the new package separately and supply the OLD project folder as TargetPath.' }
if (-not (Test-Path -LiteralPath (Join-Path $target 'backend\api.py'))) { throw 'Target must be the existing Smart ERP project root containing backend\api.py.' }
$active = @(Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue)
if ($active.Count -gt 0) { throw 'Port 8766 is running. Stop Smart ERP / Docker first, then run the upgrade. No files were changed.' }
$backup = "$target.backup_before_v630_$(Get-Date -Format yyyyMMdd_HHmmss)"
New-Item -ItemType Directory -Path $backup | Out-Null
# Back up application and data, without copying virtual environments/node_modules.
$protected = @('backend','frontend','scripts','tests','working_scripts','data','projects','workflows','approval_plans','reports','artifacts','uploaded_scripts')
foreach ($folder in $protected) {
    $from = Join-Path $target $folder
    if (Test-Path -LiteralPath $from) { Copy-Item -LiteralPath $from -Destination $backup -Recurse -Force }
}
Get-ChildItem -LiteralPath $target -File | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $backup -Force }
Write-Host "Backup created: $backup" -ForegroundColor Cyan
foreach ($folder in @('backend','frontend','scripts','tests')) {
    Copy-Item -LiteralPath (Join-Path $source $folder) -Destination $target -Recurse -Force
}
foreach ($file in @('run.py','requirements.txt','Dockerfile','docker-compose.yml','.env.example','.gitignore','.dockerignore','START_HERE_V630.md','VERIFICATION_V630.md','1_START_DOCKER_WINDOWS.ps1','Start-Windows.ps1','Start-Windows.bat','Install-Windows.ps1','Install-Windows.bat')) {
    Copy-Item -LiteralPath (Join-Path $source $file) -Destination (Join-Path $target $file) -Force
}
# Never overwrite a user's locally edited script.
$scriptRoot = Join-Path $source 'working_scripts'
Get-ChildItem -LiteralPath $scriptRoot -Recurse -File | ForEach-Object {
    $relative = $_.FullName.Substring($scriptRoot.Length).TrimStart('\')
    $destination = Join-Path (Join-Path $target 'working_scripts') $relative
    if (-not (Test-Path -LiteralPath $destination)) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $destination
    } else { Write-Host "Preserved your script: $relative" -ForegroundColor Yellow }
}
$python = Join-Path $target '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $python) {
    & $python -m pip install -r (Join-Path $target 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw "Dependency update failed. Backup is at $backup. Rerun Install-Windows.bat before starting." }
    & $python -m playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw "Chromium update failed. Backup is at $backup. Rerun Install-Windows.bat before starting." }
} else { Write-Host 'No virtual environment found. Run Install-Windows.bat (or rebuild with START_WITH_DOCKER.bat).' -ForegroundColor Yellow }
Write-Host 'Code upgraded. Your data and .env were preserved.' -ForegroundColor Green
Write-Host 'Fill the four ERPQA_KAGAMI_*_PASSWORD entries in your existing .env if missing.'
Write-Host 'Read START_HERE_V630.md. Start the app and hard-refresh the dashboard with Ctrl+F5.'
