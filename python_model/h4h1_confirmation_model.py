"""
H4/H1 Confirmation Model - Confirms or Rejects D1 Bias
Purpose: Confirm or reject the D1 bias signal

Outputs:
- confirmation: 'CONFIRM' | 'REJECT' | 'NEUTRAL'
- confidence: float [0.0, 1.0]

Rules:
- If confirmation conflicts with D1 bias → NO_TRADE
- If confirmation confidence below threshold → NO_TRADE
"""

import pandas as pd
import numpy as np
import pickle
from pathlib import Path
import json
from datetime import datetime

from data_manager import get_data_manager
from features import compute_indicators, get_feature_columns
from calibration import ModelCalibrator


def load_config():
    """Load configuration"""
    path = Path(__file__).parent / 'config.json'
    with open(path, 'r') as f:
        return json.load(f)


class H4H1ConfirmationModel:
    """
    H4/H1 Confirmation Model - Confirms or rejects D1 bias.
    
    Uses H4 as primary, H1 as secondary confirmation.
    
    Outputs:
    - confirmation: 'CONFIRM', 'REJECT', or 'NEUTRAL'
    - confidence: float [0.0, 1.0]
    """
    
    PRIMARY_TIMEFRAME = '4h'
    SECONDARY_TIMEFRAME = '1h'
    
    def __init__(self, config=None):
        """
        Initialize H4/H1 confirmation model.
        
        Args:
            config: Configuration dict
        """
        self.config = config or load_config()
        self.base_dir = Path(__file__).parent
        self.data_manager = get_data_manager()
        
        # Load models and calibrators for both timeframes
        self.models = {}
        self.calibrators = {}
        self._load_artifacts()
        
        # Confirmation thresholds from config
        self.confirmation_config = self.config.get('h4h1_confirmation', {
            'min_confidence': 0.55,
            'confirm_threshold': 0.60,  # Above this = CONFIRM
            'reject_threshold': 0.40,  # Below this = REJECT
            'require_both': False  # If True, both H4 and H1 must agree
        })
    
    def _load_artifacts(self):
        """Load trained models and calibrators for H4 and H1"""
        for tf in [self.PRIMARY_TIMEFRAME, self.SECONDARY_TIMEFRAME]:
            # Load model
            model_path = self.base_dir / f'xgb_{tf}.pkl'
            if model_path.exists():
                try:
                    with open(model_path, 'rb') as f:
                        self.models[tf] = pickle.load(f)
                except Exception as e:
                    print(f"[WARN] Failed to load {tf} model: {e}")
            
            # Load calibrator
            calibrator = ModelCalibrator(tf)
            if calibrator.load(str(self.base_dir)):
                self.calibrators[tf] = calibrator
            else:
                self.calibrators[tf] = calibrator  # Use uncalibrated
    
    def predict_confirmation(self, d1_bias, update_data=True):
        """
        Predict confirmation of D1 bias using H4/H1.
        
        Args:
            d1_bias: D1 bias dict from D1BiasModel (must have 'bias' key)
            update_data: If True, fetch latest data before prediction
            
        Returns:
            dict: {
                'confirmation': 'CONFIRM' | 'REJECT' | 'NEUTRAL',
                'confidence': float,
                'h4_result': dict,
                'h1_result': dict,
                'alignment': 'ALIGNED' | 'CONFLICT' | 'NEUTRAL',
                'timestamp': str
            }
        """
        try:
            d1_bias_value = d1_bias.get('bias', 'NEUTRAL')
            
            # Predict for H4 (primary)
            h4_result = self._predict_single_timeframe(
                self.PRIMARY_TIMEFRAME, 
                update_data
            )
            
            # Predict for H1 (secondary)
            h1_result = self._predict_single_timeframe(
                self.SECONDARY_TIMEFRAME,
                update_data
            )
            
            # Determine confirmation based on D1 bias alignment
            min_conf = self.confirmation_config.get('min_confidence', 0.55)
            confirm_thresh = self.confirmation_config.get('confirm_threshold', 0.60)
            reject_thresh = self.confirmation_config.get('reject_threshold', 0.40)
            require_both = self.confirmation_config.get('require_both', False)
            
            # Check alignment with D1 bias
            h4_direction = 'BULLISH' if h4_result['probability'] > 0.5 else 'BEARISH'
            h1_direction = 'BULLISH' if h1_result['probability'] > 0.5 else 'BEARISH'
            
            # Determine if H4/H1 confirm D1 bias
            h4_confirms = (d1_bias_value == 'BULLISH' and h4_direction == 'BULLISH') or \
                         (d1_bias_value == 'BEARISH' and h4_direction == 'BEARISH')
            
            h1_confirms = (d1_bias_value == 'BULLISH' and h1_direction == 'BULLISH') or \
                         (d1_bias_value == 'BEARISH' and h1_direction == 'BEARISH')
            
            # Calculate combined confidence
            h4_conf = h4_result['confidence']
            h1_conf = h1_result['confidence']
            combined_confidence = (h4_conf + h1_conf) / 2.0
            
            # Determine confirmation status
            if require_both:
                # Both must confirm
                if h4_confirms and h1_confirms and combined_confidence >= confirm_thresh:
                    confirmation = 'CONFIRM'
                    alignment = 'ALIGNED'
                elif (not h4_confirms and not h1_confirms) or combined_confidence <= reject_thresh:
                    confirmation = 'REJECT'
                    alignment = 'CONFLICT'
                else:
                    confirmation = 'NEUTRAL'
                    alignment = 'NEUTRAL'
            else:
                # Primary (H4) is main signal, H1 is secondary
                if h4_confirms and h4_conf >= confirm_thresh:
                    confirmation = 'CONFIRM'
                    alignment = 'ALIGNED' if h1_confirms else 'PARTIAL'
                elif not h4_confirms or h4_conf <= reject_thresh:
                    confirmation = 'REJECT'
                    alignment = 'CONFLICT'
                else:
                    confirmation = 'NEUTRAL'
                    alignment = 'NEUTRAL'
            
            # Check minimum confidence threshold
            if combined_confidence < min_conf:
                confirmation = 'NEUTRAL'
            
            return {
                'confirmation': confirmation,
                'confidence': float(combined_confidence),
                'h4_result': h4_result,
                'h1_result': h1_result,
                'alignment': alignment,
                'd1_bias': d1_bias_value,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                'confirmation': 'NEUTRAL',
                'confidence': 0.0,
                'h4_result': {'error': str(e)},
                'h1_result': {'error': str(e)},
                'alignment': 'ERROR',
                'timestamp': datetime.now().isoformat()
            }
    
    def _predict_single_timeframe(self, timeframe, update_data=True):
        """
        Predict for a single timeframe (H4 or H1).
        
        Returns:
            dict: {
                'direction': 'BULLISH' | 'BEARISH',
                'probability': float,
                'confidence': float,
                'error': str (optional)
            }
        """
        try:
            # Get latest data
            if update_data:
                self.data_manager.fetch_incremental_update(timeframe)
            
            df = self.data_manager.get_data_for_prediction(timeframe, lookback=300)
            
            if df is None or len(df) < 200:
                return {
                    'direction': 'NEUTRAL',
                    'probability': 0.5,
                    'confidence': 0.0,
                    'error': 'Insufficient data'
                }
            
            # Compute features
            df_features = compute_indicators(df)
            feature_cols = get_feature_columns()
            feature_cols = [c for c in feature_cols if c in df_features.columns]
            
            # Get latest features
            latest_features = df_features[feature_cols].iloc[-1:].values
            
            if timeframe not in self.models or self.models[timeframe] is None:
                return {
                    'direction': 'NEUTRAL',
                    'probability': 0.5,
                    'confidence': 0.0,
                    'error': 'Model not loaded'
                }
            
            # Predict
            raw_prob = self.models[timeframe].predict_proba(latest_features)[0, 1]
            
            # Calibrate
            if timeframe in self.calibrators and hasattr(self.calibrators[timeframe], 'calibrate'):
                calibrated_prob = self.calibrators[timeframe].calibrate([raw_prob])[0]
            else:
                calibrated_prob = raw_prob
            
            # Determine direction and confidence
            direction = 'BULLISH' if calibrated_prob > 0.5 else 'BEARISH'
            confidence = max(calibrated_prob, 1.0 - calibrated_prob)
            
            return {
                'direction': direction,
                'probability': float(calibrated_prob),
                'confidence': float(confidence)
            }
            
        except Exception as e:
            return {
                'direction': 'NEUTRAL',
                'probability': 0.5,
                'confidence': 0.0,
                'error': str(e)
            }
    
    def get_confirmation_status(self, d1_bias):
        """Get current confirmation status"""
        return self.predict_confirmation(d1_bias, update_data=False)


def main():
    """Test H4/H1 confirmation model"""
    from d1_bias_model import D1BiasModel
    
    # Get D1 bias first
    d1_model = D1BiasModel()
    d1_bias = d1_model.predict_bias()
    
    # Get confirmation
    conf_model = H4H1ConfirmationModel()
    result = conf_model.predict_confirmation(d1_bias)
    
    print("\n" + "="*60)
    print("H4/H1 CONFIRMATION MODEL TEST")
    print("="*60)
    print(f"D1 Bias: {d1_bias['bias']} ({d1_bias['confidence']:.2%})")
    print(f"\nConfirmation: {result['confirmation']}")
    print(f"Confidence: {result['confidence']:.2%}")
    print(f"Alignment: {result['alignment']}")
    print(f"\nH4: {result['h4_result'].get('direction', 'N/A')} "
          f"({result['h4_result'].get('confidence', 0):.2%})")
    print(f"H1: {result['h1_result'].get('direction', 'N/A')} "
          f"({result['h1_result'].get('confidence', 0):.2%})")
    print("="*60)


if __name__ == "__main__":
    main()



