# Trading Confidence Thresholds - Optimized Based on Model Accuracy

## Model Performance (Jan 5, 2026)

| Timeframe | Test Accuracy | Recommendation | Signal Status |
|-----------|--------------|-----------------|--------------|
| **1d**    | 55.24%       | ✅ Trade        | Best |
| **30m**   | 53.82%       | ✅ Trade        | Good |
| **4h**    | 50.95%       | ⚠️ Moderate     | Fair |
| **15m**   | 51.57%       | ⚠️ Moderate     | Fair |
| **1h**    | 46.87%       | ❌ Block        | Unreliable |

---

## Confidence Thresholds (Updated)

Your app now uses **timeframe-specific confidence gates** that match model performance:

### Minimum Confidence Required for Trades

```json
{
  "15m": 52%,    // 51.57% accuracy → require 52% confidence
  "30m": 54%,    // 53.82% accuracy → require 54% confidence
  "1h":  60%,    // 46.87% accuracy → require 60% (blocks most signals)
  "4h":  53%,    // 50.95% accuracy → require 53% confidence
  "1d":  55%     // 55.24% accuracy → require 55% confidence
}
```

### Minimum Risk Management Threshold

```
Global minimum: 52% (base threshold)
High confidence: 60% (considered strong signal)
```

---

## Signal Generation Rules

### 🟢 WILL TRADE (Green Light)

- **1d**: Confidence ≥ 55% 
- **30m**: Confidence ≥ 54%
- **4h**: Confidence ≥ 53%
- **15m**: Confidence ≥ 52%

### 🟡 REVIEW SIGNAL (Yellow Light)

- **1h**: Confidence ≥ 60% (very rare, model is poor)
- Calibration drift > 15% → risk reduction activated
- HTF conflict detected → risk cut by 50%

### 🔴 NO TRADE (Red Light)

- Confidence below thresholds
- 1h timeframe confidence < 60%
- High-impact news event
- Market regime = RANGE
- Calibration drift > 25% (critical)

---

## How This Works in Practice

### Example 1: 30m Signal
```
Model predicts: UP with 55% confidence
Check: 55% > 54% threshold ✅
Result: TRADE with 100% risk allocation
```

### Example 2: 1h Signal  
```
Model predicts: UP with 58% confidence
Check: 58% < 60% threshold ❌
Result: NO_TRADE - confidence too low
```

### Example 3: 1d Signal
```
Model predicts: DOWN with 56% confidence
Check: 56% > 55% threshold ✅
Result: TRADE with 100% risk allocation
```

---

## Implementation Details

**Files Updated:**
- `config.json` - Added `min_confidence_by_timeframe`
- `rules_engine.py` - Now checks timeframe-specific thresholds

**Signal Flow:**
1. Model generates probability prediction
2. Calibration adjusts probability (improves accuracy)
3. Rules engine checks confidence vs. timeframe threshold
4. If confidence too low → `NO_TRADE` with `LOW_CONFIDENCE` code
5. If passes → Continue to other checks (HTF alignment, regime, news, etc.)

---

## Expected Live Performance

With these thresholds, you should expect:
- **~51-55% Win Rate** on actual trades (matching backtest)
- **Lower false signals** (only trade high-confidence setups)
- **Better risk/reward** (fewer mediocre trades)
- **1h timeframe blocked** for most signals (unreliable model)

---

## Note on Probability Calibration

Your calibrator now:
- Adjusts raw model probabilities to match actual accuracy
- Improves Brier score by 0.3-2% on each timeframe
- Reduces overfitting bias (57% prob → 54% prob, etc.)

This means **your calibrated confidence is already reality-adjusted** - when it says 54%, that's approximately the real-world accuracy.

