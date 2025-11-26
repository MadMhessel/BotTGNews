@echo off
TITLE News Bot Launcher

echo [STATUS] Launcher started.
echoIf you see this message, the file is readable.
echo.

:: 1. Navigate to current folder
cd /d "%~dp0"

:: 2. Check Python
echo [STATUS] Checking Python...
python --version
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit
)

:: 3. Create Virtual Environment
IF NOT EXIST ".venv" (
    echo [STATUS] Creating virtual environment...
    python -m venv .venv
)

:: 4. Activate Virtual Environment
echo [STATUS] Activating environment...
call .venv\Scripts\activate.bat

:: 5. Install libraries
echo [STATUS] Installing dependencies...
python -m pip install --upgrade pip
python -m pip install aiogram google-genai python-dotenv Pillow

:: 6. Run Bot
echo.
echo [STATUS] Starting bot...
python main.py

echo.
echo [STATUS] Bot stopped.
pause