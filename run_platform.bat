@echo off
title Industrial Knowledge Intelligence Platform Launcher
echo ====================================================================
echo Starting Industrial Knowledge Intelligence Platform
echo ====================================================================

:: Add Node.js and npm to PATH (supporting both C: and D: drive installations)
set PATH=D:\Program Files\nodejs;C:\Program Files\nodejs;%APPDATA%\npm;%PATH%

:: Detect Python environment (directly check E:\et hack\backend\venv, backend\venv, backend\.venv, or system python)
set "PYTHON_CMD=E:\et hack\backend\venv\Scripts\python.exe"
if not exist "%PYTHON_CMD%" (
    if exist "backend\venv\Scripts\python.exe" (
        set "PYTHON_CMD=venv\Scripts\python.exe"
    ) else if exist "backend\.venv\Scripts\python.exe" (
        set "PYTHON_CMD=.venv\Scripts\python.exe"
    ) else if exist "venv\Scripts\python.exe" (
        set "PYTHON_CMD=..\venv\Scripts\python.exe"
    ) else if exist ".venv\Scripts\python.exe" (
        set "PYTHON_CMD=..\.venv\Scripts\python.exe"
    ) else (
        set "PYTHON_CMD=python"
    )
)

echo Using Python path for backend: %PYTHON_CMD%

echo [1/2] Starting FastAPI Backend on http://localhost:8000...
start "IKIP Backend" cmd /k "cd backend && "%PYTHON_CMD%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

echo [2/2] Starting React Frontend on http://localhost:5173...
start "IKIP Frontend" cmd /k "cd frontend && npm run dev -- --host 127.0.0.1 --port 5173"

echo ====================================================================
echo Both servers have been launched in separate cmd windows.
echo - Backend API:       http://localhost:8000
echo - API Status:        http://localhost:8000/status
echo - API Documentation: http://localhost:8000/docs
echo - Frontend Dashboard: http://localhost:5173
echo ====================================================================
pause

