@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Stop-Smart-ERP-Web.ps1" -TargetPath "%~dp0"
if errorlevel 1 (
  echo Could not safely stop the server. Review the process details above.
)
pause
