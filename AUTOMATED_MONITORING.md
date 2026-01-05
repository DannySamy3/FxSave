# Automated Paper Trading Monitor

## Overview

The `auto_paper_trade_monitor.py` script automates the entire paper trading workflow by:

1. **Starting paper trading** in the background
2. **Monitoring calibration drift** at regular intervals (every 30 minutes)
3. **Verifying system integrity** at regular intervals (every 60 minutes)
4. **Logging all activities** to `auto_monitor.log`

---

## Usage

### Basic Usage
```powershell
cd D:\CODE\Gold-Trade\python_model
python auto_paper_trade_monitor.py
```

### What It Does

1. **Starts Paper Trading**
   - Runs `live_predictor.py --paper_trade --duration 24h`
   - Runs in background (non-blocking)
   - Generates predictions every 5 minutes (300 seconds)

2. **Monitors Calibration Drift**
   - Runs `monitor_calibration_drift.py` every 30 minutes
   - Checks for excessive drift (>15%)
   - Logs warnings and recommendations

3. **Verifies System Integrity**
   - Runs `verify_system_integrity.py` every 60 minutes
   - Checks all system components
   - Validates log schema, models, calibrators, cache

4. **Logs Everything**
   - All output written to `auto_monitor.log`
   - Timestamped entries
   - Thread-safe logging

---

## Configuration

Edit the script to customize:

```python
# CONFIGURATION
PAPER_TRADE_DURATION = "24h"   # Paper trading duration
PAPER_TRADE_INTERVAL = 300     # Interval in seconds for prediction cycle
DRIFT_CHECK_INTERVAL = 1800    # Check calibration drift every 30 minutes
INTEGRITY_CHECK_INTERVAL = 3600 # Verify system integrity every 60 minutes
```

**Intervals:**
- `PAPER_TRADE_INTERVAL`: How often predictions are generated (default: 300s = 5 min)
- `DRIFT_CHECK_INTERVAL`: How often to check calibration drift (default: 1800s = 30 min)
- `INTEGRITY_CHECK_INTERVAL`: How often to verify system (default: 3600s = 60 min)

---

## Output

### Console Output
```
======================================================================
Gold-Trade Pro v2.2.0 - Automated Paper Trading + Monitoring
======================================================================
Started: 2026-01-04 12:00:00

Configuration:
  Paper Trading Duration: 24h
  Prediction Interval: 300 seconds
  Drift Check Interval: 1800 seconds (30 minutes)
  Integrity Check Interval: 3600 seconds (60 minutes)

======================================================================

[2026-01-04 12:00:00] [INFO] Starting paper trading session...
[2026-01-04 12:00:02] [INFO] Paper trading started successfully
[2026-01-04 12:00:02] [INFO] Starting calibration drift monitoring thread...
[2026-01-04 12:00:02] [INFO] Starting system integrity verification thread...

======================================================================
MONITORING ACTIVE
======================================================================
Paper trading: Running in background
Drift monitoring: Every 30 minutes
Integrity checks: Every 60 minutes
Log file: auto_monitor.log

Press Ctrl+C to stop all processes
======================================================================
```

### Log File (`auto_monitor.log`)
All activities are logged with timestamps:
```
[2026-01-04 12:00:00] [INFO] Automated Paper Trading Monitor Started
[2026-01-04 12:00:00] [INFO] Starting paper trading session...
[2026-01-04 12:00:02] [INFO] Paper trading started successfully
[2026-01-04 12:01:00] [INFO] Running: Calibration drift monitor
[2026-01-04 12:01:05] [INFO] Completed: Calibration drift monitor
[2026-01-04 12:02:00] [INFO] Running: System integrity check
[2026-01-04 12:02:10] [INFO] Completed: System integrity check
```

---

## Stopping the Monitor

**Press `Ctrl+C`** to stop all processes gracefully:
- Paper trading process is terminated
- Monitoring threads stop
- Final status is logged

---

## Features

### Thread-Safe Logging
- All threads log to the same file safely
- Timestamped entries
- Error handling for log file issues

### Process Management
- Paper trading runs as background process
- Monitoring runs in daemon threads
- Graceful shutdown on Ctrl+C

### Error Handling
- Verifies all required scripts exist before starting
- Checks if paper trading process starts successfully
- Handles thread deaths gracefully
- Logs all errors

### Status Monitoring
- Checks if paper trading process is still running
- Monitors thread health
- Reports completion status

---

## Example Workflow

1. **Start Monitor:**
   ```powershell
   python auto_paper_trade_monitor.py
   ```

2. **Let It Run:**
   - Paper trading generates predictions every 5 minutes
   - Drift monitoring checks every 30 minutes
   - Integrity checks run every 60 minutes
   - All logged to `auto_monitor.log`

3. **Check Logs:**
   ```powershell
   Get-Content auto_monitor.log -Tail 50
   ```

4. **Stop When Done:**
   - Press `Ctrl+C`
   - All processes stop gracefully

---

## Troubleshooting

**Issue: Script exits immediately**
- Check: All required scripts exist (`live_predictor.py`, `monitor_calibration_drift.py`, `verify_system_integrity.py`)
- Check: Python environment is correct

**Issue: Paper trading doesn't start**
- Check: `live_predictor.py` works standalone
- Check: No port conflicts or file locks
- Check: Sufficient disk space for logs

**Issue: Monitoring threads don't run**
- Check: Log file for error messages
- Check: Scripts are executable
- Check: Python paths are correct

**Issue: Log file not created**
- Check: Write permissions in `python_model` directory
- Check: Disk space available

---

## Integration with Other Tools

The automated monitor works seamlessly with:

- **`configure_news_keys.py`**: Configure API keys before starting
- **`monitor_calibration_drift.py`**: Called automatically every 30 min
- **`verify_system_integrity.py`**: Called automatically every 60 min
- **`live_predictor.py`**: Runs paper trading in background

---

## Best Practices

1. **Before Starting:**
   - Run `verify_system_integrity.py` manually first
   - Configure news API keys if needed
   - Ensure sufficient disk space

2. **During Monitoring:**
   - Check `auto_monitor.log` periodically
   - Review drift warnings
   - Monitor system resources

3. **After Completion:**
   - Review `forward_test_log.csv` for predictions
   - Check `auto_monitor.log` for any warnings
   - Run `monitor_calibration_drift.py` for final analysis

---

## Summary

The automated monitor provides:
- ✅ **Hands-free operation**: Start once, monitor automatically
- ✅ **Comprehensive logging**: All activities timestamped
- ✅ **Multi-threaded**: Paper trading + monitoring run concurrently
- ✅ **Graceful shutdown**: Clean termination on Ctrl+C
- ✅ **Error handling**: Robust error detection and logging

**Perfect for 24-hour paper trading tests!**






