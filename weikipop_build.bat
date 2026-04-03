@echo off
cd /d "%~dp0"
title Weikipop Builder

echo ============================================================
echo  Weikipop Build Script
echo ============================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.11-3.13 from python.org
    pause & exit /b 1
)

:: Install/check build deps
echo Installing build dependencies...
pip install pyinstaller >nul 2>&1
pip install -r requirements.txt >nul 2>&1

:: Build dictionary if missing
if not exist "dictionary.pkl" (
    echo Building dictionary ^(one-time, may take a minute^)...
    python -m scripts.build_dictionary
    if errorlevel 1 (
        echo ERROR: Dictionary build failed.
        pause & exit /b 1
    )
)

:: Run PyInstaller
echo.
echo Building weikipop.exe...
pyinstaller weikipop_win_x64.spec --noconfirm

if errorlevel 1 (
    echo.
    echo ERROR: Build failed. See above for details.
    pause & exit /b 1
)

:: Copy required files next to the exe
echo.
echo Copying required files to dist\...
if not exist "dist" mkdir dist
copy /Y "dictionary.pkl" "dist\dictionary.pkl" >nul
copy /Y "config.ini" "dist\config.ini" >nul

:: Clear Windows icon cache
echo Clearing icon cache...
taskkill /f /im explorer.exe >nul 2>&1
del /f /q "%localappdata%\IconCache.db" >nul 2>&1
del /f /q "%localappdata%\Microsoft\Windows\Explorer\iconcache*" >nul 2>&1
start explorer.exe

echo.
echo ============================================================
echo  Done! dist\ contains:
echo    weikipop.exe   - the program
echo    dictionary.pkl - required dictionary
echo    config.ini     - Wei's personal settings
echo ============================================================
echo.
pause
