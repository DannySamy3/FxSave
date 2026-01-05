# 🥇 Gold Price Prediction System - Setup Guide

## ⚡ 5-Minute Quick Start

Follow these steps in order:

### 1️⃣ Install Node.js Dependencies

```bash
npm install
```

### 2️⃣ Install Python Dependencies

```bash
cd python_model
pip install -r requirements.txt
cd ..
```

### 3️⃣ Train the Model (First Time Only)

```bash
cd python_model
python train.py
cd ..
```

⏱️ **Takes 2-5 minutes on first run** (downloads historical data and trains)

Creates:

- `python_model/gold_xgb_model.pkl` (trained model)
- `python_model/gold_data.csv` (historical data)

### 4️⃣ Generate Prediction

```bash
cd python_model
python predict.py
cd ..
```

Creates:

- `public/latest_prediction.json` (prediction data)

### 5️⃣ Run the App

```bash
npm run dev
```

Open **http://localhost:3000** 🚀

---

## 📋 What You Should See

A beautiful dashboard showing:

- ✅ Gold price direction (UP 📈 or DOWN 📉)
- ✅ Confidence percentage (e.g., 58%)
- ✅ Current Gold price in USD
- ✅ Probability distribution (UP vs DOWN)
- ✅ Last update timestamp

---

## 🔄 Daily Workflow

To get fresh predictions every day:

### Option A: Manual

```bash
cd python_model
python predict.py
cd ..
# Then refresh browser at http://localhost:3000
```

### Option B: Automated (Recommended)

**On Windows:**

1. Open Task Scheduler
2. Create New Task
3. Set trigger: Daily at 9:00 AM
4. Set action: `python C:\path\to\project\python_model\predict.py`

**On Mac/Linux:**

```bash
crontab -e
# Add this line:
0 9 * * * cd /path/to/project && python python_model/predict.py
```

---

## 🔁 Monthly Retraining

To retrain with all historical data (including recent market data):

```bash
cd python_model
python train.py    # Downloads latest data, retrains model
python predict.py  # Generates new prediction
cd ..
npm run dev        # Run frontend and refresh browser
```

---

## 🐛 Common Issues & Solutions

### ❌ "Model not found"

```
Error: Model not found at gold_xgb_model.pkl
```

**Fix:** Run `python train.py` first

### ❌ "Prediction file not found"

```
Error: Prediction file not found
```

**Fix:** Run `python predict.py` first

### ❌ "No module named 'xgboost'"

```
ModuleNotFoundError: No module named 'xgboost'
```

**Fix:** Run `pip install -r requirements.txt`

### ❌ "Port 3000 already in use"

```
Error: listen EADDRINUSE: address already in use :::3000
```

**Fix:** Use different port:

```bash
npm run dev -- -p 3001
```

### ❌ Connection timeout from Yahoo Finance

```
Error downloading data from Yahoo Finance
```

**Fix:** Check internet connection. This only happens during `train.py`.

---

## 📁 Key Files & What They Do

| File                              | Purpose                                   |
| --------------------------------- | ----------------------------------------- |
| `python_model/train.py`           | Downloads data & trains XGBoost model     |
| `python_model/predict.py`         | Generates `latest_prediction.json`        |
| `python_model/gold_xgb_model.pkl` | ⭐ Trained model (created by train.py)    |
| `pages/api/predict.js`            | API endpoint (reads JSON)                 |
| `pages/index.js`                  | Frontend dashboard                        |
| `public/latest_prediction.json`   | Latest prediction (created by predict.py) |

---

## 🎯 Expected Output

After running `python predict.py`, you should see:

```
============================================================
Gold (XAUUSD) Price Prediction - Inference
============================================================
✓ Model loaded from gold_xgb_model.pkl
📥 Downloading latest Gold data (100 days)...
✓ Downloaded 100 candles
🔮 Making prediction...
✓ Prediction: UP (Confidence: 57.23%)
  Current Gold Price: $2156.45
✓ Prediction saved to public/latest_prediction.json

============================================================
✅ Prediction Complete!
============================================================

Prediction saved to: public/latest_prediction.json
The Next.js app will read this file automatically.
```

Then `latest_prediction.json` will look like:

```json
{
  "prediction": "UP",
  "confidence": 57.23,
  "probability_down": 42.77,
  "probability_up": 57.23,
  "current_price": 2156.45,
  "timestamp": "2024-01-10 15:30:00",
  "model_version": "XGBoost v1.0",
  "generated_at": "2024-01-10 16:45:30 UTC"
}
```

---

## 💡 Pro Tips

1. **Update Daily**: Run `predict.py` daily for fresh predictions
2. **Monitor Accuracy**: Track which predictions turned out correct
3. **Use as Signal**: Combine with your own analysis, don't trade blindly
4. **Risk Management**: Always use stop losses and proper position sizing
5. **Combine Methods**: Use this prediction + price action + support/resistance

---

## 📊 Model Information

- **Algorithm**: XGBoost Classifier
- **Features**: 9 technical indicators (EMA, RSI, ATR, MACD, etc.)
- **Training Data**: 4+ years of daily Gold prices
- **Accuracy**: ~50-58% (better than random)
- **Prediction Time**: <100ms
- **Model Size**: ~1-2 MB

---

## 🔒 Privacy

✅ All data is local  
✅ No API keys needed  
✅ No cloud syncing  
✅ No user data collection  
✅ Works completely offline after initial setup

---

## 📚 Need More Help?

1. Check the main [README.md](./README.md)
2. Review comments in Python scripts
3. Check [Next.js docs](https://nextjs.org/docs)
4. Check [XGBoost docs](https://xgboost.readthedocs.io/)

---

**You're all set! 🚀 Happy predicting!**
