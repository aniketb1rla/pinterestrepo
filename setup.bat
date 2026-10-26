@echo off
cd /d "%~dp0"
where python >nul 2>nul || (echo Install Python 3.10+ from python.org first & pause & exit /b 1)
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
if not exist .env copy .env.example .env
echo.
echo Setup done. Next:  .venv\Scripts\python -m src.login
pause
