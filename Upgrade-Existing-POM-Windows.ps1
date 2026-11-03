# Safe v6.2.2 code-only upgrade. Execute from the extracted v6.2.2 source folder.
param([Parameter(Mandatory=$true)][string]$TargetPath)
$ErrorActionPreference='Stop'
$source=(Resolve-Path -LiteralPath $PSScriptRoot).Path
$target=(Resolve-Path -LiteralPath $TargetPath).Path
if ($source -eq $target) { throw 'Source and target are the same. Use Start-Desktop-Windows.bat to run the new project directly.' }
foreach ($item in @('run.py','backend\api.py','frontend\index.html')) {
  if (-not (Test-Path -LiteralPath (Join-Path $target $item))) { throw "Wrong Smart ERP project root (missing $item)" }
}
$inUse=Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue
if ($inUse) { throw 'Stop the server listening on 8766 before upgrading. Existing projects are not modified.' }
$files=@(
 'backend\api.py', 'backend\pom_bundle.py', 'frontend\app.js', 'frontend\index.html',
 'tests\test_pom_bundle_v622.py', 'POM_GENERATOR_GUIDE.md', 'V6_CHANGELOG.md',
 'desktop\package.json'
)
foreach ($backendFile in (Get-ChildItem -LiteralPath (Join-Path $source 'backend') -Filter '*.py' -File)) {
  $relative = 'backend\' + $backendFile.Name
  if (-not (Test-Path -LiteralPath (Join-Path $target $relative))) { $files += $relative }
}
$files = @($files | Select-Object -Unique)
foreach ($relative in $files) {
  if (-not (Test-Path -LiteralPath (Join-Path $source $relative))) { throw "Missing package file $relative" }
}
$backup=Join-Path $target ('backup_before_pom_v622_'+(Get-Date -Format 'yyyyMMdd_HHmmss'))
foreach ($relative in $files) {
  $dst=Join-Path $target $relative
  if (Test-Path -LiteralPath $dst) {
    $old=Join-Path $backup $relative
    New-Item -ItemType Directory -Path (Split-Path $old -Parent) -Force | Out-Null
    Copy-Item -LiteralPath $dst -Destination $old -Force
  }
  New-Item -ItemType Directory -Path (Split-Path $dst -Parent) -Force | Out-Null
  Copy-Item -LiteralPath (Join-Path $source $relative) -Destination $dst -Force
  Write-Host "Updated $relative"
}
Write-Host "Smart ERP QA v6.2.2 POM update installed. Backups: $backup" -ForegroundColor Green
Write-Host 'Existing .env, data, projects, saved workflows, approval plans, and recorded results were NOT changed.'
Write-Host 'Restart Smart ERP Desktop with Start-Desktop-Windows.bat, then reload the dashboard.'
