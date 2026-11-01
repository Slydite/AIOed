@echo off
cd /d "%~dp0"
echo Stopping AIOed background service...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*main.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host 'Stopped process' $_.ProcessId }"
echo Done.
pause
