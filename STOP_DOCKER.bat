@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp02_STOP_DOCKER_WINDOWS.ps1"
pause
