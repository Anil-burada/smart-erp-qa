# Run this on your OLD laptop, inside its actual Smart ERP QA project folder.
# Backup includes projects, workflows, approval plans and SQLite history.
# It deliberately excludes .env, .venv, and passwords configured there.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$backup = Join-Path $PSScriptRoot 'smart_erp_private_data_backup.zip'
if (Test-Path -LiteralPath $backup) {
    throw 'Backup ZIP already exists. Rename/move it before creating another backup.'
}
$dirs = @('projects','workflows','approval_plans','data')
$present = @()
foreach ($d in $dirs) {
    if (Test-Path -LiteralPath (Join-Path $PSScriptRoot $d)) { $present += (Join-Path $PSScriptRoot $d) }
}
if ($present.Count -eq 0) { throw 'No data folders found; open this script from your existing project directory.' }
Compress-Archive -LiteralPath $present -DestinationPath $backup -CompressionLevel Optimal
Write-Host "Created private data backup: $backup" -ForegroundColor Green
Write-Host 'WARNING: This may contain internal ERP URLs, workflow details, user IDs and run history. Transfer privately.' -ForegroundColor Yellow
Write-Host 'The .env file (passwords/API keys) is NOT included.'
