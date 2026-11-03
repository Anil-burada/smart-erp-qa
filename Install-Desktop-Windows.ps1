# Install Desktop dependencies in the selected Smart ERP QA project.
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
if (-not (Test-Path (Join-Path $root 'run.py'))) { throw 'Installer must be inside the project folder containing run.py' }
if (Test-Path 'C:\Program Files\nodejs\node.exe') {
    $env:Path = 'C:\Program Files\nodejs;' + $env:Path
}
$npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npm) { throw 'npm.cmd not found. Install Node.js LTS, restart VS Code, and retry.' }
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Push-Location $root
    try { py -3 -m venv .venv; if ($LASTEXITCODE -ne 0) {throw 'Failed to create virtual environment'} }
    finally { Pop-Location }
}
if (-not (Test-Path $python)) {throw 'Python not found. Install Python 3.11+.'}
& $python -m pip install -r (Join-Path $root 'requirements.txt')
if ($LASTEXITCODE -ne 0) {throw 'Python dependency installation failed'}
Push-Location (Join-Path $root 'desktop')
try {
    & $npm.Source install --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) {throw 'Electron installation failed'}
} finally {Pop-Location}
Write-Host 'Desktop setup complete. Start with .\Start-Desktop-Windows.bat' -ForegroundColor Green
