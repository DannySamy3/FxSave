@echo off
REM Gold Price Prediction System - Windows Batch Script
REM This script automates training and prediction for Windows users

setlocal enabledelayedexpansion

echo.
echo =============================================
echo Gold Price Prediction System - Setup Helper
echo =============================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python from https://www.python.org/
    pause
    exit /b 1
)

REM Check if Node.js is installed
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js is not installed or not in PATH
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

echo [OK] Python is installed: 
python --version

echo [OK] Node.js is installed:
node --version

echo.
echo Select an option:
echo 1. Install dependencies (first time only)
echo 2. Train the model (first time + monthly updates)
echo 3. Generate prediction (daily)
echo 4. Run the app (start Next.js server)
echo 5. Full setup (1 + 2 + 3)
echo 6. Daily update (3 + reload app)
echo.

set /p choice="Enter your choice (1-6): "

if "%choice%"=="1" (
    echo.
    echo Installing Node.js dependencies...
    call npm install
    echo.
    echo Installing Python dependencies...
    cd python_model
    call pip install -r requirements.txt
    cd ..
    echo [DONE] Dependencies installed!
)

if "%choice%"=="2" (
    echo.
    echo Training the model (this may take 3-5 minutes)...
    cd python_model
    call python train.py
    cd ..
    echo [DONE] Model trained!
)

if "%choice%"=="3" (
    echo.
    echo Generating prediction...
    cd python_model
    call python predict.py
    cd ..
    echo [DONE] Prediction generated!
    echo Refresh your browser to see the latest prediction.
)

if "%choice%"=="4" (
    echo.
    echo Starting Next.js development server...
    echo Open browser at http://localhost:3000
    call npm run dev
)

if "%choice%"=="5" (
    echo.
    echo === Full Setup ===
    echo Installing Node.js dependencies...
    call npm install
    echo.
    echo Installing Python dependencies...
    cd python_model
    call pip install -r requirements.txt
    cd ..
    echo.
    echo Training the model (this may take 3-5 minutes)...
    cd python_model
    call python train.py
    cd ..
    echo.
    echo Generating prediction...
    cd python_model
    call python predict.py
    cd ..
    echo [DONE] Setup complete!
    echo.
    echo Starting Next.js server...
    call npm run dev
)

if "%choice%"=="6" (
    echo.
    echo Generating fresh prediction...
    cd python_model
    call python predict.py
    cd ..
    echo [DONE] Prediction generated!
    echo.
    echo Refresh your browser to see the latest prediction.
    echo.
    pause
)

echo.
pause
