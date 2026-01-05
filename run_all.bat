@echo off
setlocal enabledelayedexpansion

title Gold Trade - Full System (App + Auto-Trainer)
color 0A
echo.
echo ======================================================================
echo    GOLD TRADE - COMPLETE SYSTEM STARTUP
echo ======================================================================
echo.
echo Starting BOTH SERVICES:
echo   [1] Next.js Web App Server (Port 3000)
echo   [2] Auto-Trainer Scheduler (Daily retraining at 5 PM)
echo.
echo ======================================================================
echo.

REM Start Next.js Web App in its own window
echo Starting Web App...
start "Gold Trade Web App - npm run dev" cmd /k "cd /d d:\CODE\Gold-Trade && echo. && echo ===== WEB APP RUNNING ON PORT 3000 ===== && echo. && npm run dev"

REM Wait for web app to initialize
echo Waiting for web app to start (3 seconds)...
timeout /t 3 /nobreak

REM Start Auto-Trainer Scheduler in its own window
echo Starting Auto-Trainer Scheduler...
start "Gold Trade Auto-Trainer - Daily Scheduler" cmd /k "cd /d d:\CODE\Gold-Trade\python_model && echo. && echo ===== AUTO-TRAINER SCHEDULER RUNNING ===== && echo. && python daily_scheduler.py"

REM Show status
echo.
echo ======================================================================
echo SUCCESS! Both services are now running:
echo.
echo   WEB APP:         http://localhost:3000
echo   AUTO-TRAINER:    Waiting for 5 PM (17:00) daily
echo.
echo New windows will open for each service.
echo Keep this window open. Close it to stop everything.
echo.
echo ======================================================================
echo.

REM Keep main window open
pause
