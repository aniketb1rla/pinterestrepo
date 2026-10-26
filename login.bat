@echo off
cd /d "%~dp0"
echo Opening Pinterest login window...
.venv\Scripts\python.exe -m src.login
pause
