# Multi-Timeframe Hierarchical Architecture

## Overview

The Gold-Trade Pro system has been upgraded to a multi-timeframe hierarchical architecture with clear responsibility separation, improved accuracy, and strict risk controls.

## Architecture Layers

### 1. D1 Bias Model (`d1_bias_model.py`)
**Timeframe:** Daily (D1)  
**Purpose:** Market bias only (BULLISH / BEARISH / NEUTRAL)

**Outputs:**
- Directional bias
- Bias confidence score

**Restrictions:**
- ❌ No entry decisions
- ❌ No position sizing

**Usage Rule:**
- If bias confidence < configurable threshold → force NO_TRADE

### 2. H4/H1 Confirmation Model (`h4h1_confirmation_model.py`)
**Timeframes:** H4 primary, H1 secondary  
**Purpose:** Confirm or reject the D1 bias

**Outputs:**
- CONFIRM / REJECT / NEUTRAL
- Confirmation confidence

**Rules:**
- If confirmation conflicts with D1 bias → NO_TRADE
- If confirmation confidence below threshold → NO_TRADE

### 3. M15/M5 Entry Engine (`m15m5_entry_engine.py`)
**Timeframes:** M15 (structure), M5 (execution)  
**Purpose:** Precise entries only

**Implementation:**
- Rule-based initially (recommended)
- Optional ML later

**Entry Patterns:**
- Break & retest
- Liquidity sweep + confirmation candle
- Trend continuation pullback

**Restrictions:**
- ❌ Cannot override higher timeframes
- ❌ Cannot trade against confirmed bias

### 4. Confidence Gate (`confidence_gate.py`)
**Purpose:** Hierarchical confidence validation

**Gates:**
1. IF D1 confidence < D1_MIN → NO_TRADE
2. IF H4/H1 confirmation != CONFIRM → NO_TRADE
3. IF entry conditions not met → NO_TRADE
4. ELSE → TRADE_ALLOWED

**Each layer logs:**
- Raw confidence
- Calibrated confidence
- Drift status

### 5. Trade Decision Engine (`trade_decision_engine.py`)
**Purpose:** Final arbiter (cannot be overridden)

**Behavioral Rules:**
- NO_TRADE is a valid success outcome
- Capital protection overrides signal frequency
- If data freshness, confidence, or alignment is uncertain → block trade
- Deterministic decisions only (same input → same output)

## Continuous Scheduler

The `continuous_scheduler.py` runs continuously and automatically executes:
1. Daily CSV updates (after market close)
2. Model retraining (D1, H4, H1 independently)

### Usage

```bash
# Run in foreground (blocking)
python continuous_scheduler.py

# Run in background (non-blocking)
python continuous_scheduler.py --background

# Check status
python continuous_scheduler.py --status
```

### Configuration

Edit `config.json`:
```json
{
  "continuous_scheduler": {
    "enabled": true,
    "check_interval": 60,
    "market_close_hour": 17,
    "market_close_minute": 0
  }
}
```

## Daily Updates

### CSV Updates (`daily_csv_update.py`)

Updates separate CSV files per timeframe:
- `cache/GC_F_1d.csv` (D1 data)
- `cache/GC_F_4h.csv` (H4 data)
- `cache/GC_F_1h.csv` (H1 data)
- `cache/GC_F_30m.csv` (30m data)
- `cache/GC_F_15m.csv` (M15 data)

Also maintains legacy `gold_data.csv` for backward compatibility.

```bash
# Update all timeframes (default)
python daily_csv_update.py

# Update specific timeframe
python daily_csv_update.py --timeframe 1d

# Force update
python daily_csv_update.py --force
```

### Model Retraining (`daily_model_update.py`)

Retrains models independently:
- D1 model (bias layer)
- H4 model (confirmation layer)
- H1 model (confirmation layer)

```bash
# Retrain all (D1, H4, H1)
python daily_model_update.py

# Retrain specific timeframe
python daily_model_update.py --timeframe 1d

# Full retrain
python daily_model_update.py --full-retrain
```

## Live Predictions

### Standard Mode (Legacy)

```python
from live_predictor import LivePredictor

predictor = LivePredictor()
results = predictor.predict_all_timeframes(update_data=True)
```

### Hierarchical Mode (New)

```python
from live_predictor import LivePredictor

predictor = LivePredictor()
decision = predictor.predict_hierarchical(update_data=True)
```

The hierarchical mode uses the full multi-timeframe architecture:
1. D1 Bias → Permission
2. H4/H1 Confirmation → Validation
3. M15/M5 Entry → Execution
4. Confidence Gate → Final Check
5. Trade Decision → Final Arbiter

## Configuration

Enable multi-timeframe architecture in `config.json`:

```json
{
  "multi_timeframe": {
    "enabled": true,
    "hierarchical_flow": true,
    "strict_gating": true
  },
  "d1_bias": {
    "min_confidence": 0.55,
    "neutral_threshold": 0.45,
    "bullish_threshold": 0.55
  },
  "h4h1_confirmation": {
    "min_confidence": 0.55,
    "confirm_threshold": 0.60,
    "reject_threshold": 0.40,
    "require_both": false
  },
  "m15m5_entry": {
    "min_structure_bars": 20,
    "retest_tolerance_pct": 0.5,
    "liquidity_sweep_lookback": 10,
    "confirmation_candles": 1,
    "trend_continuation_lookback": 5
  },
  "confidence_gates": {
    "d1_min_confidence": 0.55,
    "h4h1_min_confidence": 0.55,
    "entry_min_confidence": 0.60,
    "max_calibration_drift": 0.15,
    "block_on_drift": true
  }
}
```

## Testing Individual Components

### Test D1 Bias Model
```bash
python d1_bias_model.py
```

### Test H4/H1 Confirmation
```bash
python h4h1_confirmation_model.py
```

### Test Entry Engine
```bash
python m15m5_entry_engine.py
```

### Test Confidence Gate
```bash
python confidence_gate.py
```

### Test Trade Decision Engine
```bash
python trade_decision_engine.py
```

## Key Principles

1. **Higher timeframes give permission**
   - D1 bias must be BULLISH or BEARISH (not NEUTRAL)
   - D1 confidence must meet minimum threshold

2. **Lower timeframes ask for entry**
   - M15/M5 can only execute if D1 and H4/H1 approve
   - Entry patterns must align with confirmed bias

3. **No permission = no trade**
   - If any layer blocks, trade is blocked
   - NO_TRADE is a valid and successful outcome

4. **Capital protection overrides signal frequency**
   - Better to miss trades than take bad trades
   - Strict confidence gates protect capital

## Acceptance Criteria

The system is considered correct if:

✅ Daily model never triggers entries  
✅ Lower timeframes cannot override higher ones  
✅ Conflicting signals always result in NO_TRADE  
✅ Logs clearly explain why a trade was blocked or allowed  
✅ Backtests show fewer trades but improved drawdown control

## Migration from Legacy System

The legacy prediction system (`predict_all_timeframes`) remains available for backward compatibility. To use the new hierarchical architecture:

1. Enable in config: `"multi_timeframe": {"enabled": true}`
2. Use `predict_hierarchical()` instead of `predict_all_timeframes()`
3. Models are trained independently per timeframe
4. CSV updates maintain separate files per timeframe

## Troubleshooting

### Models Not Loading
- Ensure models are trained: `python daily_model_update.py`
- Check model files exist: `xgb_1d.pkl`, `xgb_4h.pkl`, `xgb_1h.pkl`

### No Trade Signals
- Check D1 bias confidence meets threshold
- Verify H4/H1 confirmation is CONFIRM
- Check entry engine detects valid patterns
- Review confidence gate logs

### Scheduler Not Running
- Check Python process is running
- Verify market close time configuration
- Check update logs: `logs/updates/`

## Support

For issues or questions, check:
- Update logs: `logs/updates/`
- Forward test logs: `forward_test_log.csv`
- Model backups: `backups/`

