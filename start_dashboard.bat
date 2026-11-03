@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Virtual environment missing. Please follow README installation instructions.
 pause
 exit /b 1
)
start "" "http://127.0.0.1:8766"
.venv\Scripts\python.exe run.py
pause
