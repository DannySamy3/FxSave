# Gold-Trade Pro v2.2.0 - Next Steps Guide

## ✅ Completed Fixes

All critical issues have been resolved:
- ✅ EMA_200 data destruction fixed (lookback increased to 300)
- ✅ Unicode encoding crash fixed (emojis replaced with ASCII)
- ✅ Forward test log schema fixed (23 columns)
- ✅ Regime detection verified (all timeframes return valid regimes)

---

## 📋 Next Steps

### 1. Configure News API Keys

**Option A: Interactive Configuration**
```powershell
cd D:\CODE\Gold-Trade\python_model
python configure_news_keys.py
```

**Option B: Manual Configuration**
Edit `python_model/config.json`:
```json
"news": {
  "api_keys": {
    "finnhub": "your_finnhub_api_key_here",
    "alpha_vantage": "your_alpha_vantage_key_here",
    "newsapi": "your_newsapi_key_here"
  }
}
```

**Option C: Environment Variables**
```powershell
$env:FINNHUB_API_KEY="your_key"
$env:ALPHA_VANTAGE_API_KEY="your_key"
$env:NEWSAPI_KEY="your_key"
```

**API Key Sources:**
- **Finnhub**: https://finnhub.io/register (Free tier: 60 calls/minute)
- **Alpha Vantage**: https://www.alphavantage.co/support/#api-key (Free tier: 5 calls/minute)
- **NewsAPI**: https://newsapi.org/register (Free tier: 100 requests/day)

**Note**: If keys are not configured, the system will use fallback/mock data for news integration.

---

### 2. Run 24-Hour Paper Trading Test

**Start Paper Trading:**
```powershell
cd D:\CODE\Gold-Trade\python_model
python live_predictor.py --paper_trade --duration 24h
```

**Options:**
- `--paper_trade`: Enable continuous paper trading mode
- `--duration 24h`: Run for 24 hours (or use `7d` for 7 days)
- `--interval 300`: Prediction interval in seconds (default: 300 = 5 minutes)

**What to Monitor:**
- ✅ All timeframes generate predictions without errors
- ✅ Regime detection returns valid values (not UNKNOWN)
- ✅ Risk allocation and NO_TRADE logic work correctly
- ✅ Forward test log accumulates data correctly
- ✅ News integration (if API keys configured) updates properly

**Stop Early:**
Press `Ctrl+C` to stop paper trading at any time.

---

### 3. Monitor Calibration Drift

**Check Calibration Drift:**
```powershell
cd D:\CODE\Gold-Trade\python_model
python monitor_calibration_drift.py
```

**Check Last 48 Hours:**
```powershell
python monitor_calibration_drift.py 48
```

**What to Look For:**
- ⚠️ Drift > 15% indicates potential model/calibrator mismatch
- ⚠️ If 1D or 30m show persistent high drift, retrain models

**If Retraining Needed:**
```powershell
python train.py
```

This will:
- Retrain all 5 timeframe models
- Generate fresh calibrators
- Validate Brier scores
- Save updated models and calibrators

---

### 4. Verify System Integrity

**Run Full System Check:**
```powershell
cd D:\CODE\Gold-Trade\python_model
python verify_system_integrity.py
```

**Checks Performed:**
- ✅ Forward test log: 23 columns, UTF-8 encoding
- ✅ ML models: All 5 timeframes present
- ✅ Calibrators: All 5 timeframes present
- ✅ Cache data: Sufficient historical data
- ✅ News state: File exists and updates
- ✅ API keys: Configuration status
- ✅ Regime detection: Functional test

**Expected Output:**
```
✓ All checks passed - System is ready for production
```

---

## 🔍 Verification Checklist

After completing next steps, verify:

- [ ] News API keys configured (or fallback working)
- [ ] Paper trading runs for 24 hours without errors
- [ ] Forward test log accumulates predictions correctly
- [ ] All timeframes return valid regimes (not UNKNOWN)
- [ ] Calibration drift < 15% for all timeframes
- [ ] System integrity check passes all tests
- [ ] `news_state.json` exists and updates (if news enabled)

---

## 📊 Monitoring Commands

**Quick Status Check:**
```powershell
# System integrity
python verify_system_integrity.py

# Calibration drift
python monitor_calibration_drift.py

# Single prediction test
python live_predictor.py --once
```

**View Logs:**
```powershell
# Forward test log
Get-Content forward_test_log.csv | Select-Object -Last 20

# News state
Get-Content news_state.json | ConvertFrom-Json | ConvertTo-Json
```

---

## 🚀 Production Deployment

Once all checks pass:

1. **Final Verification:**
   ```powershell
   python verify_system_integrity.py
   ```

2. **Start Live Trading (if ready):**
   ```powershell
   python live_predictor.py --paper_trade --duration 7d
   ```

3. **Monitor Performance:**
   - Check forward test log daily
   - Monitor calibration drift weekly
   - Review NO_TRADE reasons for patterns
   - Adjust risk parameters if needed

---

## 📝 Notes

- **Paper Trading**: All predictions are logged but no actual trades are executed
- **News Integration**: Works with fallback data if API keys not configured
- **Model Retraining**: Recommended monthly or when calibration drift exceeds 15%
- **Cache Updates**: Automatic incremental updates every prediction cycle

---

## 🆘 Troubleshooting

**Issue: Regime detection returns UNKNOWN**
- ✅ Fixed: Ensure lookback=300 in data retrieval
- Verify: `python verify_system_integrity.py` should pass regime test

**Issue: Forward test log has wrong schema**
- ✅ Fixed: Old log backed up, new 23-column schema created
- Verify: Check log header has 23 columns

**Issue: Unicode encoding errors**
- ✅ Fixed: Emojis replaced with ASCII in forward_test.py
- Verify: No errors when running live_predictor.py

**Issue: News integration not working**
- Check: API keys configured in config.json
- Check: `news_state.json` exists after first prediction
- Fallback: System works without news (uses mock data)

---

**System Status**: ✅ Production-Ready (after fixes applied)

**Last Updated**: January 4, 2026






