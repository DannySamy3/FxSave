@echo off
REM Gold Trading System - Daily Auto Trainer Task Scheduler Setup
REM This script creates a Windows Task Scheduler task to run daily training at 5 PM ET

echo Setting up Windows Task Scheduler for Gold Trading System...
echo.

REM Get Python path
for /f "delims=" %%i in ('python -c "import sys; print(sys.executable)"') do set PYTHON_PATH=%%i

REM Get current directory
cd /d "%~dp0"
set SCRIPT_PATH=%cd%\run_daily_updates.py

echo Python Path: %PYTHON_PATH%
echo Script Path: %SCRIPT_PATH%
echo.

REM Create the scheduled task
REM Note: Times are in LOCAL time, not ET. Adjust MARKET_CLOSE_HOUR based on your timezone offset
REM ET is UTC-5 (EST) or UTC-4 (EDT)
REM To run at 5 PM ET:
REM  - If you're in EST (UTC-5): Set trigger to 17:00 (5 PM)
REM  - If you're in EDT (UTC-4): Set trigger to 17:00 (5 PM)
REM  - Adjust based on your LOCAL time

echo Creating scheduled task: GoldTrading_DailyAutoTrainer
echo Trigger: Daily at 17:00 (5 PM) local time
echo Task: python run_daily_updates.py
echo.

REM Create task with admin privileges required
schtasks /create /tn "GoldTrading_DailyAutoTrainer" ^
    /tr "python \"%SCRIPT_PATH%\"" ^
    /sc daily ^
    /st 17:00 ^
    /f

if %errorlevel% equ 0 (
    echo.
    echo ✅ Task created successfully!
    echo.
    echo Task Details:
    echo   Name: GoldTrading_DailyAutoTrainer
    echo   Trigger: Daily at 17:00 (5 PM)
    echo   Action: python run_daily_updates.py
    echo.
    echo You can view/edit the task in Task Scheduler:
    echo   Start ^> Task Scheduler ^> Task Scheduler Library ^> GoldTrading_DailyAutoTrainer
    echo.
) else (
    echo.
    echo ❌ Error creating task. Make sure to run this script as Administrator.
    echo.
)

pause
