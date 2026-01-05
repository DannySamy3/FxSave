# Structured Error Handling Implementation Plan

## Summary

Replace generic "Live prediction failed" with structured error handling that:
1. Categorizes failures with explicit error codes
2. Implements automatic recovery where safe
3. Enforces capital safety (NO_TRADE on failures)
4. Provides specific UI messages
5. Logs all failures comprehensively

## Implementation Approach

### Phase 1: Error Infrastructure (Complete)
- ✅ Created `prediction_errors.py` with error codes and structured errors

### Phase 2: Integration Points

#### 2.1 Update `live_predictor.py`
Key changes needed:
1. Import `prediction_errors` module
2. Wrap `predict_single_timeframe` with error handling
3. Add recovery logic for data fetch, model loading
4. Return structured error results instead of generic errors

#### 2.2 Update API (`pages/api/live-predict.js`)
1. Parse structured error output from Python
2. Return error codes and messages to frontend
3. Handle timeouts and execution failures

#### 2.3 Update UI (`pages/index.js`)
1. Map error codes to specific UI messages
2. Display structured error information
3. Show recovery status

#### 2.4 Update Logging
1. Log all error codes, stages, recovery attempts
2. Ensure audit trail completeness

## Key Code Patterns

### Error Handling Pattern
```python
try:
    # Operation
    result = perform_operation()
except Exception as e:
    error = PredictionError(
        error_code=ErrorCode.OPERATION_FAILED,
        failure_stage=FailureStage.OPERATION_STAGE,
        message=str(e),
        recoverable=True,
        details=str(e)
    )
    # Try recovery
    if error.recoverable:
        error.recovery_attempted = True
        try:
            result = recover_operation()
            error.recovery_success = True
        except:
            error.recovery_success = False
            return create_no_trade_result(error, timeframe)
    else:
        return create_no_trade_result(error, timeframe)
```

### Recovery Patterns
1. **Data Fetch**: Retry once with force refresh
2. **Model Loading**: Lazy reload if missing
3. **Cache**: Refresh if stale
4. **Calibrator**: Use uncalibrated if missing (non-blocking)

## Capital Safety Guarantee

All error paths return:
```python
{
    'decision': 'NO_TRADE',
    'setup': {
        'risk_pct': 0.0,
        'risk_amount': 0.0,
        'lots': 0.0
    }
}
```

## Next Steps

1. Integrate error handling into `predict_single_timeframe`
2. Add recovery logic for critical failures
3. Update API to parse structured errors
4. Update UI to show specific messages
5. Add comprehensive logging

