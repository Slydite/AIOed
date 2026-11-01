@echo off
setlocal enabledelayedexpansion
title AIOed Installer

echo ========================================================
echo        AIOed - DeepCool LM360 Display Manager
echo                 Automatic Installer
echo ========================================================
echo.

cd /d "%~dp0"

:: 1. Check for Python
echo [1/5] Checking Python installation...
set "PY_CMD="

python --version >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=python"
    goto :FoundPython
)

py -3 --version >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=py -3"
    goto :FoundPython
)

python3 --version >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=python3"
    goto :FoundPython
)

echo.
echo [ERROR] Python 3.10+ was not found on your system!
echo Please download and install Python from: https://www.python.org/downloads/
echo IMPORTANT: Make sure to check "Add Python to PATH" during installation.
echo.
pause
exit /b 1

:FoundPython
echo       Found Python: !PY_CMD!
echo.

:: 2. Setup Virtual Environment
echo [2/5] Setting up Python virtual environment (.venv)...
if not exist ".venv\Scripts\python.exe" (
    echo       Creating virtual environment...
    !PY_CMD! -m venv .venv
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo       Virtual environment already exists.
)
echo.

:: 3. Install Dependencies
echo [3/5] Installing required packages from requirements.txt...
.\.venv\Scripts\python.exe -m pip install --quiet --upgrade pip
.\.venv\Scripts\python.exe -m pip install --quiet -r requirements.txt
if !errorlevel! neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo       Dependencies installed successfully.
echo.

:: 4. Create Desktop & Start Menu Shortcuts
echo [4/5] Creating Desktop & Start Menu shortcuts...
cscript //nologo create_shortcuts.vbs
echo       Desktop shortcut "AIOed Dashboard" created!
echo.

:: 5. Autostart Option
echo [5/5] Background Service & Autostart
set /p AUTOSTART="Enable AIOed to run automatically at Windows startup? (Y/n): "
if /i "!AUTOSTART!"=="" set "AUTOSTART=Y"
if /i "!AUTOSTART!"=="Y" (
    reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "AIOed_LM360" /t REG_SZ /d "wscript.exe \"%~dp0run_background.vbs\"" /f >nul 2>&1
    echo       Autostart enabled in Windows Registry!
) else (
    echo       Autostart skipped.
)
echo.

echo ========================================================
echo             Installation Complete!
echo ========================================================
echo.
echo You can open the AIOed Dashboard anytime by:
echo  1. Double-clicking the "AIOed Dashboard" desktop shortcut
echo  2. Opening http://localhost:5220 in your browser
echo  3. Right-clicking the AIOed system tray icon
echo.

set /p START_NOW="Would you like to start AIOed right now? (Y/n): "
if /i "!START_NOW!"=="" set "START_NOW=Y"
if /i "!START_NOW!"=="Y" (
    start "" wscript.exe "%~dp0open_dashboard.vbs"
)

echo.
pause
