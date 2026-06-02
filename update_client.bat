@echo off
title G-Byke ERP — Client Update
color 0A

echo ================================================
echo   G-Byke ERP — Laptop Update Script
echo ================================================
echo.
echo Updating G-Byke ERP on this laptop...
echo.

cd /d C:\gbyke_erp

call venv\Scripts\activate

echo [1/2] Downloading latest version...
git pull origin main
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Could not download update.
    echo Make sure this laptop has internet access.
    pause
    exit /b 1
)

echo.
echo [2/2] Installing any new packages...
pip install -r requirements.txt --quiet

echo.
echo ================================================
echo   Update complete!
echo   You can now close this window and open
echo   G-Byke ERP normally.
echo ================================================
pause