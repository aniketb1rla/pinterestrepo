@echo off
cd /d "%~dp0"
if "%~1"=="" (
    echo Pinterest Reference Downloader
    echo Usage: download.bat ^<pin_url_or_id^> [options]
    echo Example: download.bat "https://www.pinterest.com/pin/123456789/"
    echo Example: download.bat "123456789" -o ./downloads
    echo.
    set /p PIN_TARGET="Enter Pin URL, Pin ID, or Board URL: "
    if not "%PIN_TARGET%"=="" (
        .venv\Scripts\python.exe -m src.download "%PIN_TARGET%"
    )
) else (
    .venv\Scripts\python.exe -m src.download %*
)
pause
