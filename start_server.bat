@echo off
title G-Byke ERP Server
color 0A

echo ================================================
echo   G-Byke ERP — Starting Server
echo ================================================
echo.
echo Server is starting. Do NOT close this window.
echo All factory laptops connect through this window.
echo.

cd /d C:\gbyke_erp
call venv\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 8000