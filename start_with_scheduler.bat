@echo off
REM Gold Trading System - Development Mode Launcher
REM Starts Next.js dev server + Python scheduler simultaneously

echo.
echo ======================================================================
echo   GOLD TRADING SYSTEM - DEVELOPMENT MODE
echo ======================================================================
echo.
echo Starting:
echo   1. Next.js Frontend (npm run dev)
echo   2. Python Scheduler (background predictions + daily training)
echo.
echo ======================================================================
echo.

REM Start the scheduler in background
echo [Scheduler] Starting Python scheduler service...
start "Gold Trading Scheduler" python "%~dp0start_scheduler.py"

REM Give scheduler time to start
timeout /t 2 /nobreak

REM Start Next.js dev server (blocks until stopped)
echo [Frontend] Starting Next.js development server...
echo.
call npm run dev

REM Cleanup when done
echo.
echo ======================================================================
echo Development session ended
echo ======================================================================
pause
