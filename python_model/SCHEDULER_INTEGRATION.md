# Gold Trading System - Scheduler Integration

## Overview

The scheduler has been updated to integrate **daily automatic model training** with the prediction system. When the app is running (either `npm run dev` or production build), the system will:

1. **Automatically generate predictions** on candle completion
2. **Automatically retrain models daily at 5 PM ET** with new market data
3. **Load newly trained models** for live predictions

## Quick Start

### Development Mode (npm run dev)

**Option 1: Integrated Startup (Easiest)**
```bash
# From project root
start_with_scheduler.bat
```

This starts:
- Next.js dev server on port 3000
- Python scheduler in background for predictions + training

**Option 2: Manual Startup**
```bash
# Terminal 1: Frontend
npm run dev

# Terminal 2: Scheduler (python_model directory)
python start_scheduler.py
```

### Production Build

```bash
# Build the app
npm run build

# Start scheduler + app
python python_model/start_scheduler.py &
npm run start
```

## How It Works

### Prediction Scheduling
- Runs continuously in background thread
- Checks for prediction updates every 60 seconds
- Respects market hours (Gold trades ~23h/day)
- Generates predictions at candle boundaries:
  - 15m: Every 15 minutes
  - 30m: Every 30 minutes
  - 1h: Every hour
  - 4h: Every 4 hours
  - 1d: Once per day at 6 PM ET

### Daily Model Training
- **Triggered**: 5 PM ET (17:00 local time)
- **Frequency**: Once per day
- **Process**:
  1. Fetches latest market data (including previous day's close)
  2. Updates feature calculations
  3. Retrains all 5 timeframe models (15m, 30m, 1h, 4h, 1d)
  4. Validates new models against old ones
  5. Deploys only if performance improved
  6. Creates backups of old models
- **Models Updated**: `xgb_*.pkl` and `calibrator_*.pkl`
- **Status**: Logged to console

## Configuration

Edit `scheduler.py` to customize:

```python
scheduler.retrain_hour = 17      # Time to run training (5 PM ET = 17)
scheduler.check_interval = 60    # Check frequency (seconds)
scheduler.enable_retraining = True  # Set to False to disable training
```

## Troubleshooting

### Training Not Running
1. **Check time**: Is it past 5 PM ET?
2. **Check console**: Look for "🧠 DAILY MODEL RETRAINING" message
3. **Check models**: Should see timestamps updated after 5 PM ET
   ```bash
   Get-Item 'python_model/xgb_*.pkl' | Select-Object Name, LastWriteTime
   ```

### Training Failed
- Check `python_model/auto_daily_trainer.log` for errors
- Verify data is available: `python python_model/check_prediction.py`
- Try manual training: `python python_model/auto_daily_trainer.py`

### No Predictions
- Verify API is working: Visit `http://localhost:3000/api/predict`
- Check `latest_prediction.json` exists and is recent
- Run manual prediction: `python python_model/predict.py`

## Fixed Issues

### Issue: Models not trained with Jan 6 data
**Root Cause**: 
- Scheduler wasn't running when app was active
- Auto-trainer had yfinance MultiIndex column handling bug

**Solution**:
- Integrated training into main `scheduler.py`
- Fixed `auto_daily_trainer.py` to handle yfinance MultiIndex
- Training now runs automatically when scheduler is active

### Issue: "Data must be 1-dimensional" error
**Root Cause**: yfinance returns MultiIndex columns for single symbols

**Solution**: Added column flattening in `fetch_data()`:
```python
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)
```

## Model Training Details

### Training Metrics
Models are trained with:
- **Data**: Last ~60 days of 15m candles for short timeframes, 1 year for daily
- **Features**: Technical indicators (RSI, MACD, ATR, Bollinger Bands, etc.)
- **Validation**: 85/15 train/test split
- **Metrics Tracked**: F1-Score, Precision, Recall, Accuracy

### Deployment Logic
New models deploy only if:
- No old model exists, OR
- F1-Score improves by ≥ 0.01 (1% improvement threshold)

Regressions are prevented:
- Models kept if F1 drops by ≤ 2%
- Skipped if change is between -2% and +1%

### Backup Strategy
- Current models backed up before training
- Located in `model_backups/backup_YYYYMMDD_HHMMSS/`
- Easy rollback if needed

## Files Modified

1. **scheduler.py** - Added daily training integration
2. **auto_daily_trainer.py** - Fixed yfinance MultiIndex bug
3. **start_scheduler.py** - New launcher script
4. **start_with_scheduler.bat** - Convenient startup script

## Next Steps

For production deployment:
1. Set up Windows Task Scheduler (optional backup)
2. Monitor training success in logs
3. Adjust training hour if needed (adjust `retrain_hour`)
4. Configure risk parameters in trading logic

---

**Last Updated**: 2026-01-07  
**Scheduler Status**: ✅ Operational  
**Daily Training**: ✅ Enabled (5 PM ET)
