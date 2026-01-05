#!/bin/bash
# Gold Price Prediction System - Linux/Mac Setup Script
# This script automates training and prediction for Unix-like systems

echo ""
echo "============================================="
echo "Gold Price Prediction System - Setup Helper"
echo "============================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed"
    echo "Please install Python 3 from https://www.python.org/"
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "[ERROR] Node.js is not installed"
    echo "Please install Node.js from https://nodejs.org/"
    exit 1
fi

echo "[OK] Python is installed:"
python3 --version

echo "[OK] Node.js is installed:"
node --version

echo ""
echo "Select an option:"
echo "1. Install dependencies (first time only)"
echo "2. Train the model (first time + monthly updates)"
echo "3. Generate prediction (daily)"
echo "4. Run the app (start Next.js server)"
echo "5. Full setup (1 + 2 + 3)"
echo "6. Daily update (3 + reload app)"
echo ""

read -p "Enter your choice (1-6): " choice

case $choice in
    1)
        echo ""
        echo "Installing Node.js dependencies..."
        npm install
        echo ""
        echo "Installing Python dependencies..."
        cd python_model
        pip3 install -r requirements.txt
        cd ..
        echo "[DONE] Dependencies installed!"
        ;;
    2)
        echo ""
        echo "Training the model (this may take 3-5 minutes)..."
        cd python_model
        python3 train.py
        cd ..
        echo "[DONE] Model trained!"
        ;;
    3)
        echo ""
        echo "Generating prediction..."
        cd python_model
        python3 predict.py
        cd ..
        echo "[DONE] Prediction generated!"
        echo "Refresh your browser to see the latest prediction."
        ;;
    4)
        echo ""
        echo "Starting Next.js development server..."
        echo "Open browser at http://localhost:3000"
        npm run dev
        ;;
    5)
        echo ""
        echo "=== Full Setup ==="
        echo "Installing Node.js dependencies..."
        npm install
        echo ""
        echo "Installing Python dependencies..."
        cd python_model
        pip3 install -r requirements.txt
        cd ..
        echo ""
        echo "Training the model (this may take 3-5 minutes)..."
        cd python_model
        python3 train.py
        cd ..
        echo ""
        echo "Generating prediction..."
        cd python_model
        python3 predict.py
        cd ..
        echo "[DONE] Setup complete!"
        echo ""
        echo "Starting Next.js server..."
        npm run dev
        ;;
    6)
        echo ""
        echo "Generating fresh prediction..."
        cd python_model
        python3 predict.py
        cd ..
        echo "[DONE] Prediction generated!"
        echo ""
        echo "Refresh your browser to see the latest prediction."
        ;;
    *)
        echo "Invalid choice. Please run the script again."
        exit 1
        ;;
esac

echo ""
