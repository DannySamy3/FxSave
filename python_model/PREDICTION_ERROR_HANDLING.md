# Structured Error Handling for Live Prediction Pipeline

## Overview

This document describes the structured error handling system that replaces generic "Live prediction failed" messages with specific error codes, recovery logic, and safe NO_TRADE fallbacks.

## Error Categories

### 1. Data Errors
- `DATA_EMPTY`: No data returned from data source
- `DATA_INSUFFICIENT`: Data exists but insufficient rows (< 50 or < lookback)
- `DATA_STALE`: Data exists but is too old
- `DATA_FETCH_FAILED`: Data fetch raised exception
- `DATA_TIMEOUT`: Data fetch timed out

### 2. Feature Computation Errors
- `FEATURE_NAN`: Computed features contain NaN values
- `FEATURE_INCOMPLETE`: Features computed but incomplete (missing columns)
- `FEATURE_COMPUTE_FAILED`: Feature computation raised exception

### 3. Model Errors
- `MODEL_NOT_LOADED`: Model file missing or failed to load
- `MODEL_PREDICT_FAILED`: Model prediction raised exception
- `CALIBRATOR_NOT_LOADED`: Calibrator missing (non-critical, uses uncalibrated)
- `CALIBRATOR_FAILED`: Calibration process failed

### 4. News Errors
- `NEWS_STATE_INVALID`: News state file corrupted or invalid
- `NEWS_FETCH_FAILED`: News fetch raised exception
- `NEWS_TIMEOUT`: News fetch timed out

### 5. System Errors
- `TIMEOUT`: Overall prediction timeout (2 minutes)
- `MEMORY_ERROR`: Out of memory
- `UNKNOWN_ERROR`: Unhandled exception

## Recovery Logic

### Automatic Recovery (Safe)

1. **Data Fetch**: One retry on failure
2. **Cache Refresh**: Refresh cache if data is stale
3. **Model Reload**: Lazy reload if model missing (attempt once)
4. **Calibrator**: Use uncalibrated if calibrator missing (non-blocking)

### No Recovery (Fail Safe)

- Feature computation failures → NO_TRADE
- Model prediction failures → NO_TRADE
- News state corruption → NO_TRADE
- Timeouts → NO_TRADE

## Capital Safety

On any failure:
- `decision = NO_TRADE`
- `risk_pct = 0.0`
- `risk_amount = 0.0`
- `lots = 0.0`
- Never emit a prediction on partial or unstable inputs

## UI Messages

Each error code maps to a specific UI message:
- `DATA_EMPTY` → "⛔ NO TRADE — Insufficient fresh market data"
- `FEATURE_INCOMPLETE` → "⛔ NO TRADE — Feature computation incomplete"
- `MODEL_NOT_LOADED` → "⛔ NO TRADE — Model temporarily unavailable"
- etc.

## Logging

Every failure logs:
- `failure_code`: Error code enum value
- `failure_stage`: Stage where failure occurred
- `recovery_attempted`: Boolean
- `recovery_success`: Boolean
- `timestamp`: When failure occurred
- `details`: Additional error details



