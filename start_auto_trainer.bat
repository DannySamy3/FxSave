@echo off
title Gold Trade Auto Trainer - Always-On Scheduler
cd /d "d:\CODE\Gold-Trade\python_model"
echo.
echo ======================================================================
echo    GOLD TRADE AUTO TRAINER - Professional Always-On Scheduler
echo ======================================================================
echo.
echo Starting Auto Trainer...
echo This window will stay open and automatically run training daily at 5 PM
echo.
echo Keep this window open for continuous auto-training
echo Close this window ONLY to stop auto-training
echo.
echo ======================================================================
echo.
python daily_scheduler.py
pause
