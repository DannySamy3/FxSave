"""
Prediction Error Handling Module
Structured error codes and handling for live prediction pipeline.

Error Categories:
- DATA: Market data fetch/validation
- FEATURE: Feature computation
- MODEL: Model/calibrator loading
- NEWS: News gating/validation
- SYSTEM: System-level issues
"""

from enum import Enum
from typing import Dict, Optional
from datetime import datetime


class ErrorCode(Enum):
    """Structured error codes for prediction failures"""
    
    # Data errors
    DATA_EMPTY = "DATA_EMPTY"
    DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
    DATA_STALE = "DATA_STALE"
    DATA_FETCH_FAILED = "DATA_FETCH_FAILED"
    DATA_TIMEOUT = "DATA_TIMEOUT"
    
    # Feature computation errors
    FEATURE_NAN = "FEATURE_NAN"
    FEATURE_INCOMPLETE = "FEATURE_INCOMPLETE"
    FEATURE_COMPUTE_FAILED = "FEATURE_COMPUTE_FAILED"
    
    # Model errors
    MODEL_NOT_LOADED = "MODEL_NOT_LOADED"
    MODEL_PREDICT_FAILED = "MODEL_PREDICT_FAILED"
    CALIBRATOR_NOT_LOADED = "CALIBRATOR_NOT_LOADED"
    CALIBRATOR_FAILED = "CALIBRATOR_FAILED"
    
    # News errors
    NEWS_STATE_INVALID = "NEWS_STATE_INVALID"
    NEWS_FETCH_FAILED = "NEWS_FETCH_FAILED"
    NEWS_TIMEOUT = "NEWS_TIMEOUT"
    
    # System errors
    TIMEOUT = "TIMEOUT"
    MEMORY_ERROR = "MEMORY_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class FailureStage(Enum):
    """Stages in prediction pipeline where failures occur"""
    
    DATA_FETCH = "DATA_FETCH"
    DATA_VALIDATION = "DATA_VALIDATION"
    FEATURE_COMPUTATION = "FEATURE_COMPUTATION"
    MODEL_PREDICTION = "MODEL_PREDICTION"
    CALIBRATION = "CALIBRATION"
    NEWS_CHECK = "NEWS_CHECK"
    RISK_CALCULATION = "RISK_CALCULATION"
    RESULT_ASSEMBLY = "RESULT_ASSEMBLY"


class PredictionError(Exception):
    """
    Structured prediction error with recovery information.
    """
    
    def __init__(self, 
                 error_code: ErrorCode,
                 failure_stage: FailureStage,
                 message: str,
                 recoverable: bool = False,
                 recovery_attempted: bool = False,
                 recovery_success: bool = False,
                 details: Optional[str] = None):
        self.error_code = error_code
        self.failure_stage = failure_stage
        self.message = message
        self.recoverable = recoverable
        self.recovery_attempted = recovery_attempted
        self.recovery_success = recovery_success
        self.details = details
        self.timestamp = datetime.now()
        
        super().__init__(self.message)
    
    def to_dict(self) -> Dict:
        """Convert error to dictionary for logging/UI"""
        return {
            'error_code': self.error_code.value,
            'failure_stage': self.failure_stage.value,
            'message': self.message,
            'recoverable': self.recoverable,
            'recovery_attempted': self.recovery_attempted,
            'recovery_success': self.recovery_success,
            'details': self.details,
            'timestamp': self.timestamp.isoformat()
        }
    
    def to_ui_message(self) -> str:
        """Generate user-friendly UI message"""
        ui_messages = {
            ErrorCode.DATA_EMPTY: "⛔ NO TRADE — Insufficient fresh market data",
            ErrorCode.DATA_INSUFFICIENT: "⛔ NO TRADE — Insufficient market data",
            ErrorCode.DATA_STALE: "⛔ NO TRADE — Market data is stale",
            ErrorCode.DATA_FETCH_FAILED: "⛔ NO TRADE — Failed to fetch market data",
            ErrorCode.DATA_TIMEOUT: "⛔ NO TRADE — Market data fetch timeout",
            
            ErrorCode.FEATURE_NAN: "⛔ NO TRADE — Feature computation incomplete",
            ErrorCode.FEATURE_INCOMPLETE: "⛔ NO TRADE — Feature computation incomplete",
            ErrorCode.FEATURE_COMPUTE_FAILED: "⛔ NO TRADE — Feature computation failed",
            
            ErrorCode.MODEL_NOT_LOADED: "⛔ NO TRADE — Model temporarily unavailable",
            ErrorCode.MODEL_PREDICT_FAILED: "⛔ NO TRADE — Model prediction failed",
            ErrorCode.CALIBRATOR_NOT_LOADED: "⛔ NO TRADE — Calibrator unavailable",
            ErrorCode.CALIBRATOR_FAILED: "⛔ NO TRADE — Calibration failed",
            
            ErrorCode.NEWS_STATE_INVALID: "⛔ NO TRADE — News state invalid",
            ErrorCode.NEWS_FETCH_FAILED: "⛔ NO TRADE — News fetch failed",
            ErrorCode.NEWS_TIMEOUT: "⛔ NO TRADE — News fetch timeout",
            
            ErrorCode.TIMEOUT: "⛔ NO TRADE — Prediction timeout",
            ErrorCode.MEMORY_ERROR: "⛔ NO TRADE — System memory error",
            ErrorCode.UNKNOWN_ERROR: "⛔ NO TRADE — Unknown error occurred"
        }
        
        base_msg = ui_messages.get(self.error_code, f"⛔ NO TRADE — {self.message}")
        
        if self.recovery_attempted and not self.recovery_success:
            base_msg += " (recovery failed)"
        
        return base_msg


def create_no_trade_result(error: PredictionError, timeframe: str) -> Dict:
    """
    Create a safe NO_TRADE result from an error.
    Ensures capital safety by setting all risk to zero.
    """
    return {
        'timeframe': timeframe,
        'decision': 'NO_TRADE',
        'rejection_reason': error.error_code.value,
        'error': error.to_dict(),
        'ui_message': error.to_ui_message(),
        'confidence': 0.0,
        'direction': 'UNKNOWN',
        'setup': {
            'decision': 'NO_TRADE',
            'risk_pct': 0.0,
            'risk_amount': 0.0,
            'lots': 0.0,
            'reason': error.error_code.value
        },
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

