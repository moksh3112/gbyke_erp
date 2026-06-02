@echo off
title G-Byke ERP — Server Update
color 0A

echo ================================================
echo   G-Byke ERP — Server Update Script
echo ================================================
echo.
echo This will update the server to the latest version.
echo Please do NOT close this window until it finishes.
echo.

:: Navigate to project folder
cd /d C:\gbyke_erp

:: Activate virtual environment
call venv\Scripts\activate

:: Pull latest code from GitHub
echo [1/3] Downloading latest updates from GitHub...
git pull origin main
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Could not download updates.
    echo Make sure this PC is connected to the internet.
    pause
    exit /b 1
)

:: Install any new packages
echo.
echo [2/3] Installing any new required packages...
pip install -r requirements.txt --quiet

:: Restart the server
echo.
echo [3/3] Restarting G-Byke ERP server...
echo.

:: Kill existing uvicorn if running
taskkill /f /im uvicorn.exe >nul 2>&1
taskkill /f /im python.exe /fi "WINDOWTITLE eq G-Byke ERP Server" >nul 2>&1

:: Wait a moment
timeout /t 2 /nobreak >nul

:: Start server in a new window
start "G-Byke ERP Server" cmd /k "cd /d C:\gbyke_erp && venv\Scripts\activate && uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo.
echo ================================================
echo   Update complete! Server is restarting.
echo   This window will close in 5 seconds.
echo ================================================
timeout /t 5 /nobreak >nul