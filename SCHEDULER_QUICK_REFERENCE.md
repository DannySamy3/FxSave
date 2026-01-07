# Quick Reference - Gold Trading Scheduler

## Start the System

### Development
```bash
cd D:\CODE\Gold-Trade
start_with_scheduler.bat
```

### Or Manual (2 terminals)
**Terminal 1 - Frontend:**
```bash
cd D:\CODE\Gold-Trade
npm run dev
```

**Terminal 2 - Scheduler:**
```bash
cd D:\CODE\Gold-Trade\python_model
python start_scheduler.py
```

## What Happens Automatically

**Continuous (Every 60 seconds)**
- ✓ Check for new market data
- ✓ Generate predictions
- ✓ Update `latest_prediction.json`

**Daily at 5 PM ET**
- ✓ Fetch latest market data
- ✓ Retrain all 5 models (15m, 30m, 1h, 4h, 1d)
- ✓ Validate model performance
- ✓ Deploy if improved
- ✓ Backup old models

## Manual Commands

### Run Training Now
```bash
cd python_model
python auto_daily_trainer.py
```

### Run Predictions Now
```bash
cd python_model
python predict.py
```

### Check Model Files
```powershell
# Models
Get-Item 'python_model/xgb_*.pkl' | Select-Object Name, LastWriteTime

# Calibrators
Get-Item 'python_model/calibrator_*.pkl' | Select-Object Name, LastWriteTime

# Predictions
Get-Item 'public/latest_prediction.json' | Select-Object LastWriteTime
```

## Scheduler Disabled?

```bash
# Enable training (default)
python scheduler.py

# Disable training
python scheduler.py --no-training

# Change check interval
python scheduler.py --interval 120
```

## Troubleshooting

**"No predictions generated"**
1. Is scheduler running? Look for "Scheduler started" message
2. Is market open? Gold trades 23h/day Sun-Fri
3. Manual test: `python predict.py`

**"Training error"**
1. Check time: Is it past 5 PM ET?
2. Check data: `python check_prediction.py`
3. Manual train: `python auto_daily_trainer.py`

**"Models not updating"**
1. Verify scheduler is running
2. Check timestamps: `Get-Item 'python_model/xgb_*.pkl'`
3. Check backups: `python_model/model_backups/`

## Files to Know

| File | Purpose |
|------|---------|
| `scheduler.py` | Main prediction + training scheduler |
| `start_scheduler.py` | Launcher script |
| `auto_daily_trainer.py` | Daily model training |
| `python_model/xgb_*.pkl` | Trading models (5 timeframes) |
| `python_model/calibrator_*.pkl` | Prediction calibrators |
| `public/latest_prediction.json` | Latest predictions (API) |
| `model_backups/` | Backup of old models |

## API Endpoints

```
GET /api/predict           # Get latest predictions
GET /api/status            # Get system status
GET /api/news              # Get market news
```

## Configuration (Edit scheduler.py)

```python
scheduler.retrain_hour = 17           # Training time (5 PM ET)
scheduler.enable_retraining = True    # Enable training
scheduler.check_interval = 60         # Check frequency (seconds)
```

---

**Quick Links:**
- Full docs: `SCHEDULER_INTEGRATION.md`
- Fix details: `SCHEDULER_FIX_COMPLETE.md`
- Training logs: Check console output
- Model backups: `python_model/model_backups/`
