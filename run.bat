@echo off
setlocal
cd /d "%~dp0"

echo =========================================================
echo   ChronoDine - Enterprise Restaurant Intelligence Platform
echo =========================================================
echo.

set "PY=python"
if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"
if exist "..\venv\Scripts\python.exe" set "PY=..\venv\Scripts\python.exe"

set "PYTHONPATH=%CD%\backend"

echo Starting Backend Server on http://localhost:8000...
echo.

REM Automatically open browser after 3 seconds
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:8000"

%PY% -m uvicorn app.main:app --host 0.0.0.0 --port 8000

pause
