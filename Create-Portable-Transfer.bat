@echo off
setlocal
cd /d "%~dp0"
echo ========================================================
echo   SMART ERP QA - CREATE ONE ZIP FOR LAPTOP 2
 echo ========================================================
echo.
echo 1. Close the Smart ERP server on this laptop first.
echo 2. Paste the FULL folder path of your currently installed project.
echo.
set /p "oldroot=Current project folder: "
if not defined oldroot (
  echo No folder entered. Nothing changed.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Create-Portable-Transfer.ps1" -CurrentProjectPath "%oldroot%"
if errorlevel 1 echo Transfer ZIP creation failed. Read the error above.
pause
