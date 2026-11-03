@echo off
cd /d "%~dp0"
echo Smart ERP QA v6.2.7 - Fresh Windows installation
echo Requires Python 3.11+ and internet for pip/Playwright Chromium downloads.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-Windows.ps1"
if errorlevel 1 (
  echo Installation failed. See the message above.
) else (
  echo Installation complete. Next double-click 2_OPEN_SMART_ERP_WEB.bat.
)
pause
