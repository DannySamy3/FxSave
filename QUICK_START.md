# Gold-Trade Pro v2.2.0 - Quick Start Guide

## ✅ System Status: Production-Ready

All critical fixes have been applied and verified.

---

## 🚀 Quick Commands

### Configure News API Keys
```powershell
cd D:\CODE\Gold-Trade\python_model
python configure_news_keys.py
```

### Run 24-Hour Paper Trading
```powershell
cd D:\CODE\Gold-Trade\python_model
python live_predictor.py --paper_trade --duration 24h
```

### Monitor Calibration Drift
```powershell
cd D:\CODE\Gold-Trade\python_model
python monitor_calibration_drift.py
```

### Verify System Integrity
```powershell
cd D:\CODE\Gold-Trade\python_model
python verify_system_integrity.py
```

### Single Prediction Test
```powershell
cd D:\CODE\Gold-Trade\python_model
python live_predictor.py --once
```

---

## 📊 Current System Status

**Verified Components:**
- ✅ All 5 ML models present (15m, 30m, 1h, 4h, 1d)
- ✅ All 5 calibrators present
- ✅ Forward test log: 23 columns, UTF-8 encoding
- ✅ Cache data: All timeframes have sufficient data
- ✅ Regime detection: Working correctly (returns WEAK_TREND, not UNKNOWN)

**Expected Warnings (Normal):**
- ⚠️ News state file: Will be created on first prediction
- ⚠️ API keys: Not configured (fallback works)

---

## 📝 Next Steps Summary

1. **Configure News API Keys** (Optional)
   - Run: `python configure_news_keys.py`
   - Or edit `config.json` manually

2. **Run Paper Trading Test**
   - Run: `python live_predictor.py --paper_trade --duration 24h`
   - Monitor for errors and verify predictions

3. **Monitor Calibration Drift**
   - Run: `python monitor_calibration_drift.py`
   - Retrain if drift > 15%: `python train.py`

4. **Verify System Integrity**
   - Run: `python verify_system_integrity.py`
   - Should show all checks passing

---

## 🔍 Verification Results

**Last System Check:**
```
✓ Forward test log: 23 columns, UTF-8 encoding
✓ All 5/5 models present
✓ All 5/5 calibrators present
✓ Cache data: All timeframes populated
✓ Regime detection: WEAK_TREND (ADX: 27.2)
```

**System is ready for paper trading!**

---

For detailed instructions, see `NEXT_STEPS.md`








