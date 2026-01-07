# Gold Trading System - Automatic Scheduler Integration

## Quick Start (Easiest)

### Development Mode - Scheduler Runs Automatically
```bash
cd D:\CODE\Gold-Trade
npm run dev
```

**That's it!** The scheduler will automatically start in parallel with the Next.js dev server.

### Production Build - Scheduler Runs Automatically
```bash
cd D:\CODE\Gold-Trade
npm run build
npm start
```

Scheduler starts automatically with the production server.

---

## What Happens Automatically

When you run `npm run dev` or `npm start`:

✅ **Frontend** (Next.js)
- Starts on `http://localhost:3000`
- Loads the trading dashboard
- Serves predictions from API

✅ **Backend** (Python Scheduler)
- Starts prediction scheduler
- Checks for new data every 60 seconds
- Runs daily model training at 5 PM ET
- Updates latest predictions

✅ **Integration**
- Both run in same terminal
- Color-coded output (Next.js in color, Python output with timestamps)
- Both stop together when you press Ctrl+C

---

## How It Works

### Behind the Scenes

Modified `package.json` to use `concurrently`:
```json
"dev": "concurrently \"next dev\" \"cd python_model && python start_scheduler.py\" --kill-others",
"start": "concurrently \"next start\" \"cd python_model && python start_scheduler.py\" --kill-others"
```

This:
1. Starts Next.js dev/production server
2. Starts Python scheduler in parallel
3. Kills both when you stop with Ctrl+C

### Daily Training

**Automatic at 5 PM ET**
- Fetches latest market data
- Retrains all 5 models (15m, 30m, 1h, 4h, 1d)
- Validates performance
- Deploys if improved
- Backs up old models

### Live Predictions

**Continuous (every 60 seconds)**
- Checks for new candles
- Generates fresh predictions
- Updates `latest_prediction.json`
- Dashboard refreshes automatically

---

## Troubleshooting

### Scheduler not starting?
```
Error: Cannot find module 'concurrently'
```
**Solution**: Already installed with `npm install`, but if needed:
```bash
npm install concurrently --save
```

### Python errors?
Look for "🧠 DAILY MODEL RETRAINING" or scheduler errors in console. Models will be retrained daily automatically.

### Want to disable scheduler?
```bash
# Just run Next.js without scheduler
next dev
# or for production
next start
```

### Want to run scheduler only?
```bash
cd python_model
python start_scheduler.py
```

---

## Files Modified

- `package.json` - Added `concurrently` and updated `dev`/`start` scripts

## Files Created (from scheduler fix)

- `python_model/start_scheduler.py` - Scheduler launcher
- `python_model/scheduler.py` - Updated with training integration
- `python_model/auto_daily_trainer.py` - Fixed yfinance bug
- `SCHEDULER_QUICK_REFERENCE.md` - Quick reference
- `SCHEDULER_INTEGRATION.md` - Detailed docs

---

## Summary

✅ **Before**: Had to manually run scheduler in separate terminal  
✅ **After**: `npm run dev` starts everything automatically  
✅ **Training**: Runs daily at 5 PM ET automatically  
✅ **Zero Configuration**: Works out of the box

Just run `npm run dev` and everything works! 🚀
