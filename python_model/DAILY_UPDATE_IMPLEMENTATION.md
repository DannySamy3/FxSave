# Daily CSV Update & Model Learning - Implementation Guide

## Overview

This document describes the implementation of automatic daily CSV updates and model learning for Gold-Trade Pro v2.2.0.

---

## Components Created

### 1. `daily_csv_update.py`
**Purpose**: Automatically append new market data to `gold_data.csv` after market close.

**Features**:
- Fetches latest data from cache or Yahoo Finance
- Appends to `gold_data.csv` (deduplicates)
- Logs timestamp and row count
- Handles failures gracefully
- Prevents duplicate updates on same day

**Usage**:
```bash
# Daily update (default: 1d timeframe)
python daily_csv_update.py

# Force update even if already updated today
python daily_csv_update.py --force

# Update specific timeframe
python daily_csv_update.py --timeframe 1h
```

**Output**:
- Updates `gold_data.csv` with new rows
- Logs to `logs/csv_update_log.json`

---

### 2. `daily_model_update.py`
**Purpose**: Automatically update models with new daily data after market close.

**Features**:
- Checks for new data availability
- Runs incremental learning or full retrain
- Logs training metrics and timestamps
- Handles failures gracefully
- Minimum row threshold to avoid unnecessary retraining

**Usage**:
```bash
# Check for new data and retrain if available
python daily_model_update.py

# Force full retrain (ignore new data check)
python daily_model_update.py --full-retrain

# Update specific timeframe only
python daily_model_update.py --timeframe 1h

# Set minimum rows required
python daily_model_update.py --min-rows 5
```

**Output**:
- Updates model files (`xgb_*.pkl`, `calibrator_*.pkl`)
- Logs to `logs/model_learning_log.json`

---

### 3. `update_logger.py`
**Purpose**: Comprehensive logging system for CSV updates and model learning.

**Features**:
- JSON-based logging
- Timestamp tracking
- Success/failure status
- Audit trail for all updates
- Statistics and history queries

**Log Files**:
- `logs/csv_update_log.json`: CSV update history
- `logs/model_learning_log.json`: Model learning history

**Log Entry Format**:
```json
{
  "timestamp": "2026-01-04T18:00:00",
  "operation": "csv_update",
  "timeframe": "1d",
  "status": "success",
  "rows_added": 1,
  "last_row_date": "2026-01-04",
  "error": null
}
```

**Methods**:
- `log_update(result)`: Log an update operation
- `get_last_update(operation)`: Get last update entry
- `get_update_history(operation, limit)`: Get update history
- `get_failed_updates(operation, days)`: Get failed updates
- `get_statistics(operation, days)`: Get statistics

---

## Automation Setup

### Option 1: Windows Task Scheduler

**Step 1: Create CSV Update Task**
1. Open Task Scheduler
2. Create Basic Task
3. Name: "Gold-Trade Daily CSV Update"
4. Trigger: Daily at 6:00 PM (after market close)
5. Action: Start a program
   - Program: `python`
   - Arguments: `D:\CODE\Gold-Trade\python_model\daily_csv_update.py`
   - Start in: `D:\CODE\Gold-Trade\python_model`

**Step 2: Create Model Learning Task**
1. Create Basic Task
2. Name: "Gold-Trade Daily Model Learning"
3. Trigger: Daily at 6:30 PM (after CSV update)
4. Action: Start a program
   - Program: `python`
   - Arguments: `D:\CODE\Gold-Trade\python_model\daily_model_update.py`
   - Start in: `D:\CODE\Gold-Trade\python_model`

---

### Option 2: Linux/Mac Cron

**Edit crontab**:
```bash
crontab -e
```

**Add entries**:
```cron
# Daily CSV update at 6 PM ET (18:00)
0 18 * * 1-5 cd /path/to/Gold-Trade/python_model && python daily_csv_update.py

# Daily model learning at 6:30 PM ET (18:30)
30 18 * * 1-5 cd /path/to/Gold-Trade/python_model && python daily_model_update.py
```

**Note**: Adjust timezone and path as needed.

---

### Option 3: Python Scheduler Integration

**Add to `scheduler.py`**:
```python
def run_daily_updates(self):
    """Run daily CSV update and model learning"""
    from daily_csv_update import update_gold_data_csv
    from daily_model_update import daily_model_learning
    
    # CSV update
    csv_result = update_gold_data_csv()
    if csv_result['status'] == 'success':
        # Model learning (only if CSV update succeeded)
        model_result = daily_model_learning()
        return csv_result, model_result
    else:
        print(f"⚠️ CSV update failed, skipping model learning")
        return csv_result, None
```

**Schedule in scheduler**:
```python
# Add to scheduler setup
schedule.every().day.at("18:00").do(scheduler.run_daily_updates)
```

---

## Monitoring & Alerts

### Check Log Files

**View last CSV update**:
```python
from update_logger import UpdateLogger
logger = UpdateLogger()
last = logger.get_last_update('csv_update')
print(f"Last update: {last['timestamp']}, Status: {last['status']}")
```

**View failed updates**:
```python
failed = logger.get_failed_updates('csv_update', days=7)
for entry in failed:
    print(f"{entry['timestamp']}: {entry['error']}")
```

**Get statistics**:
```python
stats = logger.get_statistics('csv_update', days=30)
print(f"Success: {stats['success']}, Failed: {stats['failed']}")
print(f"Consecutive failures: {stats['consecutive_failures']}")
```

---

### Health Check Script

Create `check_daily_updates.py`:
```python
from update_logger import UpdateLogger
from datetime import datetime, timedelta

logger = UpdateLogger()

# Check CSV updates
csv_stats = logger.get_statistics('csv_update', days=7)
if csv_stats['consecutive_failures'] > 0:
    print(f"⚠️ WARNING: {csv_stats['consecutive_failures']} consecutive CSV update failures")

# Check model learning
model_stats = logger.get_statistics('model_learning', days=7)
if model_stats['consecutive_failures'] > 0:
    print(f"⚠️ WARNING: {model_stats['consecutive_failures']} consecutive model learning failures")
```

---

## Testing

### Test CSV Update
```bash
# Test update
python daily_csv_update.py --force

# Check log
python -c "from update_logger import UpdateLogger; import json; logger = UpdateLogger(); print(json.dumps(logger.get_last_update('csv_update'), indent=2))"
```

### Test Model Learning
```bash
# Test with minimal rows
python daily_model_update.py --min-rows 0

# Check log
python -c "from update_logger import UpdateLogger; import json; logger = UpdateLogger(); print(json.dumps(logger.get_last_update('model_learning'), indent=2))"
```

---

## Troubleshooting

### CSV Update Fails

**Check**:
1. Data manager can fetch data: `python -c "from data_manager import get_data_manager; dm = get_data_manager(); print(dm.fetch_incremental_update('1d'))"`
2. `gold_data.csv` is writable
3. Log file for error details: `logs/csv_update_log.json`

### Model Learning Fails

**Check**:
1. Sufficient data available
2. Model files are writable
3. Log file for error details: `logs/model_learning_log.json`

### No Updates Happening

**Check**:
1. Scheduler/cron is running
2. Python path is correct
3. Dependencies installed
4. Log files for skipped updates

---

## Summary

✅ **CSV Updates**: Automatic daily append to `gold_data.csv`  
✅ **Model Learning**: Automatic daily model updates with new data  
✅ **Logging**: Comprehensive audit trail with timestamps  
✅ **Automation**: Ready for scheduler/cron integration  
✅ **Monitoring**: Statistics and failure tracking  

The system now ensures the model always has the latest market data for predictions.



