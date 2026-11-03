@echo off
setlocal
cd /d "%~dp0"
if exist "%ProgramFiles%\nodejs\node.exe" set "PATH=%ProgramFiles%\nodejs;%PATH%"
echo ======================================
echo   SMART ERP QA 6.2.1 DESKTOP
 echo ======================================
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Python environment missing. Run Install-Desktop-Windows.ps1 first.
  pause
  exit /b 1
)
if not exist "desktop\node_modules\electron" (
  echo [ERROR] Electron missing. Run Install-Desktop-Windows.ps1 first.
  pause
  exit /b 1
)
where npm.cmd >nul 2>&1
if errorlevel 1 (
  echo [ERROR] npm.cmd not found. Install Node.js LTS and reopen PowerShell.
  pause
  exit /b 1
)
echo A separate Python dashboard command is NOT required.
echo Logs will be saved under the project logs folder.
cd desktop
call npm.cmd start
if errorlevel 1 (
  echo.
  echo Desktop closed with an error. See ..\logs\desktop_backend.stderr.log
  pause
)
