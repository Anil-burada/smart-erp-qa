@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp01_START_DOCKER_WINDOWS.ps1"
pause
