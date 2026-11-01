@echo off
setlocal enabledelayedexpansion
title AIOed Uninstaller

echo ========================================================
echo        AIOed - DeepCool LM360 Display Manager
echo                 Uninstaller / Cleaner
echo ========================================================
echo.

cd /d "%~dp0"

echo [1/3] Stopping background services...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*main.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host 'Stopped PID' $_.ProcessId }"

echo [2/3] Removing Windows Autostart registry entry...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "AIOed_LM360" /f >nul 2>&1
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "DeepCoolLM360Display" /f >nul 2>&1

echo [3/3] Removing Desktop and Start Menu shortcuts...
powershell -NoProfile -Command "$d = [Environment]::GetFolderPath('Desktop') + '\AIOed Dashboard.lnk'; if (Test-Path $d) { Remove-Item $d -Force; Write-Host 'Removed Desktop shortcut.' }"
powershell -NoProfile -Command "$p = [Environment]::GetFolderPath('Programs') + '\AIOed Dashboard.lnk'; if (Test-Path $p) { Remove-Item $p -Force; Write-Host 'Removed Start Menu shortcut.' }"

echo.
echo ========================================================
echo AIOed has been stopped and shortcuts/autostart removed.
echo You may now safely delete this folder if desired.
echo ========================================================
echo.
pause
