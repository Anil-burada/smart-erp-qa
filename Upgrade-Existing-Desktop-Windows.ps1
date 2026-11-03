# Install v6.2.1 desktop support into an EXISTING Smart ERP QA project safely.
param([Parameter(Mandatory=$true)][string]$TargetPath)
$ErrorActionPreference='Stop'
$source=$PSScriptRoot
$target=(Resolve-Path -LiteralPath $TargetPath).Path
if ($source -eq $target) { throw 'Source and target are the same folder. Use Start-Desktop-Windows.bat in this folder instead.' }
foreach ($item in @('run.py','backend\api.py','frontend\index.html')) {
  if (-not (Test-Path (Join-Path $target $item))) { throw "Not Smart ERP QA project root: missing $item" }
}
if (Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue) { throw 'Stop the existing Smart ERP QA server on port 8766 before installing. Run Check-Desktop-Setup.ps1 to identify the process.' }
$files=@('backend\api.py','backend\browser.py','frontend\index.html','frontend\app.js','frontend\styles.css','frontend\reporting.css','frontend\reporting.js', 'Start-Desktop-Windows.bat','Install-Desktop-Windows.ps1','Check-Desktop-Setup.ps1','DESKTOP_GUIDE.md')
$files += @(Get-ChildItem -Path (Join-Path $source 'desktop') -Recurse -File | Where-Object { $_.FullName -notmatch 'node_modules' } | ForEach-Object { 'desktop\' + $_.FullName.Substring((Join-Path $source 'desktop').Length+1) })
foreach ($file in (Get-ChildItem -LiteralPath (Join-Path $source 'backend') -Filter '*.py' -File)) {
  $relative = 'backend\' + $file.Name
  if (-not (Test-Path (Join-Path $target $relative))) { $files += $relative }
}
foreach($relative in $files){if(-not(Test-Path (Join-Path $source $relative))){throw "Upgrade source missing $relative"}}
$backup=Join-Path $target ('backup_before_desktop_'+(Get-Date -Format 'yyyyMMdd_HHmmss'))
foreach($relative in $files){
  $old=Join-Path $target $relative
  $new=Join-Path $source $relative
  if(Test-Path $old){$backupFile=Join-Path $backup $relative; New-Item -Force -ItemType Directory -Path (Split-Path -Parent $backupFile) | Out-Null; Copy-Item -LiteralPath $old -Destination $backupFile -Force}
  New-Item -Force -ItemType Directory -Path (Split-Path -Parent $old) | Out-Null
  Copy-Item -LiteralPath $new -Destination $old -Force
  Write-Host "Updated $relative"
}
Write-Host "Desktop upgrade installed. Backup: $backup" -ForegroundColor Green
Write-Host 'Existing .env, data, projects, workflows, approval plans, and execution history were NOT changed.'
Write-Host 'Next: run Install-Desktop-Windows.ps1 from your EXISTING project; then Start-Desktop-Windows.bat.'
