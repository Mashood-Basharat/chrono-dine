@echo off
setlocal
cd /d "%~dp0"

echo =========================================================
echo   ChronoDine - Enterprise Restaurant Intelligence Platform
echo =========================================================
echo.

set "PY="
if exist "%~dp0venv\Scripts\python.exe" set "PY=%~dp0venv\Scripts\python.exe"
if not defined PY if exist "%~dp0..\Resturant Analysis\venv\Scripts\python.exe" set "PY=%~dp0..\Resturant Analysis\venv\Scripts\python.exe"
if not defined PY if exist "D:\Resturant Analysis\venv\Scripts\python.exe" set "PY=D:\Resturant Analysis\venv\Scripts\python.exe"
if not defined PY if exist "%~dp0..\venv\Scripts\python.exe" set "PY=%~dp0..\venv\Scripts\python.exe"
if not defined PY set "PY=python"

set "PYTHONPATH=%CD%\backend"

echo Using Python runtime: %PY%
echo Starting Backend Server on http://localhost:8000...
echo.

REM Automatically open browser after 3 seconds
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:8000"

"%PY%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000

pause
