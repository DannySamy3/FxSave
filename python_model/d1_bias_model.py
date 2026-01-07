"""
D1 Bias Model - Higher Timeframe Bias Detection
Purpose: Market bias only (BULLISH / BEARISH / NEUTRAL)

Restrictions:
- ❌ No entry decisions
- ❌ No position sizing
- Only outputs directional bias and confidence score
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


class D1BiasModel:
    """
    D1 (Daily) Bias Model - Only provides market bias, no entries.
    
    Outputs:
    - bias: 'BULLISH', 'BEARISH', or 'NEUTRAL'
    - confidence: float [0.0, 1.0]
    """
    
    TIMEFRAME = '1d'
    
    def __init__(self, config=None):
        """
        Initialize D1 bias model.
        
        Args:
            config: Configuration dict
        """
        self.config = config or load_config()
        self.base_dir = Path(__file__).parent
        self.data_manager = get_data_manager()
        
        # Load model and calibrator
        self.model = None
        self.calibrator = None
        self._load_artifacts()
        
        # Bias thresholds from config
        self.bias_config = self.config.get('d1_bias', {
            'min_confidence': 0.55,
            'neutral_threshold': 0.45,  # Below this = NEUTRAL
            'bullish_threshold': 0.55   # Above this = BULLISH
        })
    
    def _load_artifacts(self):
        """Load trained model and calibrator"""
        # Load model
        model_path = self.base_dir / f'xgb_{self.TIMEFRAME}.pkl'
        if model_path.exists():
            try:
                with open(model_path, 'rb') as f:
                    self.model = pickle.load(f)
            except Exception as e:
                print(f"⚠️ Failed to load D1 model: {e}")
        
        # Load calibrator
        self.calibrator = ModelCalibrator(self.TIMEFRAME)
        if not self.calibrator.load(str(self.base_dir)):
            print(f"⚠️ D1 calibrator not found, using uncalibrated")
    
    def predict_bias(self, update_data=True):
        """
        Predict D1 market bias.
        
        Args:
            update_data: If True, fetch latest data before prediction
            
        Returns:
            dict: {
                'bias': 'BULLISH' | 'BEARISH' | 'NEUTRAL',
                'confidence': float,
                'raw_probability': float,
                'calibrated_probability': float,
                'timestamp': str
            }
        """
        try:
            # Get latest data
            if update_data:
                self.data_manager.fetch_incremental_update(self.TIMEFRAME)
            
            df = self.data_manager.get_data_for_prediction(self.TIMEFRAME, lookback=300)
            
            if df is None or len(df) < 200:
                return {
                    'bias': 'NEUTRAL',
                    'confidence': 0.0,
                    'raw_probability': 0.5,
                    'calibrated_probability': 0.5,
                    'error': 'Insufficient data',
                    'timestamp': datetime.now().isoformat()
                }
            
            # Compute features
            df_features = compute_indicators(df)
            feature_cols = get_feature_columns()
            feature_cols = [c for c in feature_cols if c in df_features.columns]
            
            # Get latest features
            latest_features = df_features[feature_cols].iloc[-1:].values
            
            if self.model is None:
                return {
                    'bias': 'NEUTRAL',
                    'confidence': 0.0,
                    'raw_probability': 0.5,
                    'calibrated_probability': 0.5,
                    'error': 'Model not loaded',
                    'timestamp': datetime.now().isoformat()
                }
            
            # Predict
            raw_prob = self.model.predict_proba(latest_features)[0, 1]
            
            # Calibrate
            if self.calibrator and hasattr(self.calibrator, 'calibrate'):
                calibrated_prob = self.calibrator.calibrate([raw_prob])[0]
            else:
                calibrated_prob = raw_prob
            
            # Determine bias
            min_conf = self.bias_config.get('min_confidence', 0.55)
            neutral_thresh = self.bias_config.get('neutral_threshold', 0.45)
            bullish_thresh = self.bias_config.get('bullish_threshold', 0.55)
            
            if calibrated_prob < neutral_thresh:
                bias = 'BEARISH'
                confidence = 1.0 - calibrated_prob
            elif calibrated_prob > bullish_thresh:
                bias = 'BULLISH'
                confidence = calibrated_prob
            else:
                bias = 'NEUTRAL'
                confidence = min(calibrated_prob, 1.0 - calibrated_prob) * 2  # Scale to [0, 1]
            
            # Check if confidence meets minimum threshold
            if confidence < min_conf:
                bias = 'NEUTRAL'
                confidence = 0.0
            
            return {
                'bias': bias,
                'confidence': float(confidence),
                'raw_probability': float(raw_prob),
                'calibrated_probability': float(calibrated_prob),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                'bias': 'NEUTRAL',
                'confidence': 0.0,
                'raw_probability': 0.5,
                'calibrated_probability': 0.5,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def get_bias_status(self):
        """Get current bias status"""
        return self.predict_bias(update_data=False)


def main():
    """Test D1 bias model"""
    model = D1BiasModel()
    result = model.predict_bias()
    
    print("\n" + "="*60)
    print("D1 BIAS MODEL TEST")
    print("="*60)
    print(f"Bias: {result['bias']}")
    print(f"Confidence: {result['confidence']:.2%}")
    print(f"Raw Probability: {result['raw_probability']:.2%}")
    print(f"Calibrated Probability: {result['calibrated_probability']:.2%}")
    if 'error' in result:
        print(f"Error: {result['error']}")
    print("="*60)


if __name__ == "__main__":
    main()



