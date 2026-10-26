@echo off
cd /d "%~dp0"
echo Starting Pinterest Reference Gallery...
.venv\Scripts\python.exe -m src.server --port 8000 --open
pause
