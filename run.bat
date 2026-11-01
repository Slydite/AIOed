@echo off
cd /d "%~dp0"
echo Starting AIOed Controller...
if exist ".venv\Scripts\python.exe" (
    .\.venv\Scripts\python.exe main.py %*
) else (
    python main.py %*
)
pause
