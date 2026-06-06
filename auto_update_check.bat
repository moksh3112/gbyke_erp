@echo off
:: Runs every 5 minutes via Task Scheduler.
:: Checks GitHub for new commits — if found, triggers a full server update.

cd /d C:\gbyke_erp
call venv\Scripts\activate

git fetch origin main >nul 2>&1

for /f %%i in ('git rev-parse HEAD') do set LOCAL=%%i
for /f %%i in ('git rev-parse origin/main') do set REMOTE=%%i

if not "%LOCAL%"=="%REMOTE%" (
    echo [%DATE% %TIME%] New version detected. Starting update...
    call update_server.bat
)
