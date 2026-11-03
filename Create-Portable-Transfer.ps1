# Build a single full Smart ERP QA v6.3.0 Windows deployment ZIP including
# the live saved projects/workflows/history of this laptop.
# Does not change the currently installed project or copy its root .env.
param(
  [Parameter(Mandatory=$true)][string]$CurrentProjectPath,
  [string]$DestinationZip = (Join-Path $env:USERPROFILE 'Downloads\Smart_ERP_QA_Transfer_With_My_Data.zip')
)
$ErrorActionPreference = 'Stop'
$kit = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$current = (Resolve-Path -LiteralPath $CurrentProjectPath).Path
$script = Join-Path $kit 'scripts\build_portable_transfer.py'
if (-not (Test-Path -LiteralPath $script)) {
  throw 'The deployment kit is incomplete: missing scripts\build_portable_transfer.py.'
}
# Refuse to copy an open SQLite DB. Do not kill unrelated processes.
$listener = @(Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue)
if ($listener.Count -gt 0) {
  $processes = ($listener | Select-Object -ExpandProperty OwningProcess -Unique) -join ', '
  throw "Port 8766 is running (PID: $processes). Close your Smart ERP backend first, then retry."
}
$oldVenvPython = Join-Path $current '.venv\Scripts\python.exe'
$kitVenvPython = Join-Path $kit '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $oldVenvPython) {
  $python = $oldVenvPython
  $pyArgs = @()
} elseif (Test-Path -LiteralPath $kitVenvPython) {
  $python = $kitVenvPython
  $pyArgs = @()
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
  $python = 'py'
  $pyArgs = @('-3')
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
  $python = 'python'
  $pyArgs = @()
} else {
  throw 'Python 3 was not found. Install Python or use the existing project virtual environment.'
}
& $python @pyArgs $script '--kit-root' $kit '--current-project' $current '--output' $DestinationZip
if ($LASTEXITCODE -ne 0) {
  throw 'Portable export failed. The original Smart ERP project is unchanged.'
}
