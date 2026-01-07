# Calibration Drift Control System - Implementation Summary

## Overview
Implemented a robust calibration drift control system in Gold-Trade Pro v2.2.0 that protects capital when model confidence reliability degrades.

## Implementation Details

### 1. Configuration (`config.json`)
Added calibration control thresholds:
```json
"calibration_control": {
  "safe_drift": 0.15,
  "warning_drift": 0.25,
  "risk_reduction_multiplier": 0.5
}
```

### 2. Drift Evaluation Logic
For each prediction:
- `calibration_drift = abs(raw_confidence - calibrated_confidence)`
- Applied before any trade decision

**Drift Levels:**
- **drift ≤ 15% (SAFE)**: Trade normally
- **15% < drift ≤ 25% (WARNING)**: Reduce risk to 50%
- **drift > 25% (CRITICAL)**: Block trade

### 3. Risk Enforcement Rules

#### Case A: Drift Warning (15–25%)
- Allow trades only if all other filters pass
- Apply: `risk_multiplier = 0.5`
- Decision: `TRADE` (with reduced risk)
- Reason logged: `CALIBRATION_WARNING`

#### Case B: Drift Critical (>25%)
- Force:
  - `decision = NO_TRADE`
  - `risk_pct = 0`
  - `risk_amount = 0`
  - `lots = 0`
  - `reason = CALIBRATION_UNSTABLE`
- Overrides:
  - Confidence threshold
  - HTF alignment
  - Risk-reward rules
  - Regime state

**Note:** News blocks have higher priority than calibration drift.

### 4. UI Messaging (Exact Wording)

#### Risk Reduced (Warning Level)
```
⚠️ Risk Reduced
Decision: TRADE_ALLOWED
Reason: Calibration Drift (18.62%)
Risk Adjustment: 50%
```

#### Trade Blocked (Critical Level)
```
⛔ NO TRADE
Decision: NO_TRADE
Risk Allocation: 0%
Capital at Risk: $0.00
Reason: CALIBRATION_UNSTABLE
Details: Drift exceeds safe limit
```

### 5. Logging (Audit-Safe)
All fields logged into forward test schema:
- `raw_conf`: Raw model confidence
- `calib_conf`: Calibrated confidence
- `calib_drift`: Calibration drift percentage
- `risk_multiplier`: Applied risk multiplier (includes drift reduction)
- `decision`: TRADE or NO_TRADE
- `reason`: `CALIBRATION_UNSTABLE` | `CALIBRATION_WARNING` | other

**Note:** For WARNING level drift, `CALIBRATION_WARNING` is logged in the `reason` field even when decision is TRADE, to track risk reduction events for audit purposes.

### 6. Determinism & Safety
- ✅ No randomness
- ✅ No adaptive overrides
- ✅ Same inputs → same outputs
- ✅ Capital preservation > trade frequency

### 7. Integration Priority
The system applies controls in this order:
1. **News blocks** (highest priority - blocks everything)
2. **Calibration drift** (blocks or reduces risk)
3. **HTF conflicts** (reduces risk)
4. **Other filters** (regime, confidence, RR)

## Files Modified

1. **`python_model/config.json`**
   - Added `calibration_control` section
   - Added `CALIBRATION_UNSTABLE` and `CALIBRATION_WARNING` to rejection_reasons

2. **`python_model/live_predictor.py`**
   - Added drift evaluation logic after calibration
   - Applied drift-based risk reduction/blocking
   - Integrated with risk multiplier chain
   - Enhanced logging to include drift warnings

3. **`pages/index.js`**
   - Added UI display for drift warnings (risk reduced)
   - Added UI display for drift blocks (critical)
   - Updated rejection details to show drift information

## Acceptance Criteria Status

✅ Drift warnings appear in UI  
✅ Risk automatically reduced for moderate drift  
✅ Trades blocked for severe drift  
✅ Logs are complete and auditable  
✅ No conflicts with HTF, news, or regime logic  

## Design Principle

**If confidence reliability is compromised, the system must defend capital, not chase trades.**

The system prioritizes capital preservation over trade frequency. When calibration drift indicates model reliability issues, the system:
- Reduces risk exposure (warning level)
- Blocks trades entirely (critical level)

This ensures that degraded model performance does not lead to excessive risk-taking.




