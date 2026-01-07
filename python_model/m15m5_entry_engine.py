"""
M15/M5 Entry Engine - Precise Entry Detection
Purpose: Precise entries only (rule-based initially, optional ML later)

Timeframes:
- M15: Structure identification
- M5: Execution timing

Restrictions:
- ❌ Cannot override higher timeframes
- ❌ Cannot trade against confirmed bias

Entry Patterns:
- Break & retest
- Liquidity sweep + confirmation candle
- Trend continuation pullback
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime

from data_manager import get_data_manager
from features import compute_indicators


def load_config():
    """Load configuration"""
    path = Path(__file__).parent / 'config.json'
    with open(path, 'r') as f:
        return json.load(f)


class M15M5EntryEngine:
    """
    M15/M5 Entry Engine - Rule-based entry detection.
    
    Uses M15 for structure, M5 for execution timing.
    """
    
    STRUCTURE_TIMEFRAME = '15m'
    EXECUTION_TIMEFRAME = '5m'  # Note: May need to add 5m support
    
    def __init__(self, config=None):
        """
        Initialize entry engine.
        
        Args:
            config: Configuration dict
        """
        self.config = config or load_config()
        self.base_dir = Path(__file__).parent
        self.data_manager = get_data_manager()
        
        # Entry pattern configuration
        self.entry_config = self.config.get('m15m5_entry', {
            'min_structure_bars': 20,
            'retest_tolerance_pct': 0.5,  # 0.5% tolerance for retest
            'liquidity_sweep_lookback': 10,
            'confirmation_candles': 1,
            'trend_continuation_lookback': 5
        })
    
    def detect_entry(self, d1_bias, h4h1_confirmation, update_data=True):
        """
        Detect entry signals using M15/M5.
        
        Args:
            d1_bias: D1 bias dict (must have 'bias' key)
            h4h1_confirmation: H4/H1 confirmation dict (must have 'confirmation' key)
            update_data: If True, fetch latest data before detection
            
        Returns:
            dict: {
                'entry_signal': 'LONG' | 'SHORT' | 'NONE',
                'entry_type': str (pattern name),
                'confidence': float,
                'm15_structure': dict,
                'm5_execution': dict,
                'timestamp': str
            }
        """
        try:
            # Validate higher timeframe permissions
            d1_bias_value = d1_bias.get('bias', 'NEUTRAL')
            confirmation = h4h1_confirmation.get('confirmation', 'NEUTRAL')
            
            # If D1 bias is NEUTRAL or confirmation is not CONFIRM, no entry
            if d1_bias_value == 'NEUTRAL' or confirmation != 'CONFIRM':
                return {
                    'entry_signal': 'NONE',
                    'entry_type': 'NO_PERMISSION',
                    'confidence': 0.0,
                    'reason': f'D1={d1_bias_value}, Confirmation={confirmation}',
                    'timestamp': datetime.now().isoformat()
                }
            
            # Get M15 data for structure
            if update_data:
                self.data_manager.fetch_incremental_update(self.STRUCTURE_TIMEFRAME)
            
            df_m15 = self.data_manager.get_data_for_prediction(
                self.STRUCTURE_TIMEFRAME, 
                lookback=100
            )
            
            if df_m15 is None or len(df_m15) < 50:
                return {
                    'entry_signal': 'NONE',
                    'entry_type': 'INSUFFICIENT_DATA',
                    'confidence': 0.0,
                    'reason': 'Insufficient M15 data',
                    'timestamp': datetime.now().isoformat()
                }
            
            # Detect structure on M15
            m15_structure = self._detect_m15_structure(df_m15, d1_bias_value)
            
            if m15_structure['signal'] == 'NONE':
                return {
                    'entry_signal': 'NONE',
                    'entry_type': m15_structure.get('reason', 'NO_STRUCTURE'),
                    'confidence': 0.0,
                    'm15_structure': m15_structure,
                    'timestamp': datetime.now().isoformat()
                }
            
            # Get M5 data for execution (fallback to M15 if 5m not available)
            # For now, use M15 for both structure and execution
            df_m5 = df_m15  # TODO: Add proper 5m support
            
            # Detect execution timing
            m5_execution = self._detect_m5_execution(df_m5, m15_structure, d1_bias_value)
            
            if m5_execution['signal'] == 'NONE':
                return {
                    'entry_signal': 'NONE',
                    'entry_type': m5_execution.get('reason', 'NO_EXECUTION'),
                    'confidence': 0.0,
                    'm15_structure': m15_structure,
                    'm5_execution': m5_execution,
                    'timestamp': datetime.now().isoformat()
                }
            
            # Combine structure and execution confidence
            combined_confidence = (m15_structure['confidence'] + m5_execution['confidence']) / 2.0
            
            return {
                'entry_signal': m5_execution['signal'],
                'entry_type': m5_execution.get('pattern', 'UNKNOWN'),
                'confidence': float(combined_confidence),
                'm15_structure': m15_structure,
                'm5_execution': m5_execution,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                'entry_signal': 'NONE',
                'entry_type': 'ERROR',
                'confidence': 0.0,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _detect_m15_structure(self, df, expected_bias):
        """
        Detect structure on M15 timeframe.
        
        Patterns:
        - Break & retest
        - Liquidity sweep
        - Trend continuation setup
        """
        try:
            # Compute basic indicators
            df = df.copy()
            df['SMA_20'] = df['Close'].rolling(20).mean()
            df['SMA_50'] = df['Close'].rolling(50).mean()
            df['ATR'] = df['High'].rolling(14).max() - df['Low'].rolling(14).min()
            
            latest = df.iloc[-1]
            recent = df.tail(20)
            
            # Determine trend
            trend_up = latest['SMA_20'] > latest['SMA_50']
            trend_down = latest['SMA_20'] < latest['SMA_50']
            
            # Check alignment with expected bias
            if expected_bias == 'BULLISH' and not trend_up:
                return {
                    'signal': 'NONE',
                    'reason': 'Structure not aligned with BULLISH bias',
                    'confidence': 0.0
                }
            
            if expected_bias == 'BEARISH' and not trend_down:
                return {
                    'signal': 'NONE',
                    'reason': 'Structure not aligned with BEARISH bias',
                    'confidence': 0.0
                }
            
            # Pattern 1: Break & Retest
            if len(df) >= 30:
                # Look for recent breakout
                high_20 = recent['High'].max()
                low_20 = recent['Low'].min()
                
                # Check if price broke above/below recent range and retested
                if expected_bias == 'BULLISH':
                    # Look for break above and retest
                    if latest['Close'] > high_20 * 0.995:  # Near recent high
                        # Check for retest pattern
                        recent_lows = recent['Low'].tail(5)
                        if len(recent_lows) > 0:
                            min_low = recent_lows.min()
                            if latest['Close'] > min_low * 1.005:  # Retested and held
                                return {
                                    'signal': 'LONG',
                                    'pattern': 'BREAK_RETEST',
                                    'confidence': 0.7,
                                    'details': f'Break above {high_20:.2f}, retest held'
                                }
                
                elif expected_bias == 'BEARISH':
                    # Look for break below and retest
                    if latest['Close'] < low_20 * 1.005:  # Near recent low
                        # Check for retest pattern
                        recent_highs = recent['High'].tail(5)
                        if len(recent_highs) > 0:
                            max_high = recent_highs.max()
                            if latest['Close'] < max_high * 0.995:  # Retested and held
                                return {
                                    'signal': 'SHORT',
                                    'pattern': 'BREAK_RETEST',
                                    'confidence': 0.7,
                                    'details': f'Break below {low_20:.2f}, retest held'
                                }
            
            # Pattern 2: Trend Continuation Pullback
            if trend_up and expected_bias == 'BULLISH':
                # Look for pullback to SMA20/50
                if latest['Low'] <= latest['SMA_20'] * 1.002 and latest['Close'] > latest['SMA_20']:
                    return {
                        'signal': 'LONG',
                        'pattern': 'TREND_CONTINUATION',
                        'confidence': 0.65,
                        'details': 'Pullback to SMA20 in uptrend'
                    }
            
            elif trend_down and expected_bias == 'BEARISH':
                # Look for pullback to SMA20/50
                if latest['High'] >= latest['SMA_20'] * 0.998 and latest['Close'] < latest['SMA_20']:
                    return {
                        'signal': 'SHORT',
                        'pattern': 'TREND_CONTINUATION',
                        'confidence': 0.65,
                        'details': 'Pullback to SMA20 in downtrend'
                    }
            
            # No clear structure found
            return {
                'signal': 'NONE',
                'reason': 'No clear entry structure detected',
                'confidence': 0.0
            }
            
        except Exception as e:
            return {
                'signal': 'NONE',
                'reason': f'Error detecting structure: {e}',
                'confidence': 0.0
            }
    
    def _detect_m5_execution(self, df, m15_structure, expected_bias):
        """
        Detect execution timing on M5 (or M15 if 5m not available).
        
        Looks for confirmation candles and precise entry points.
        """
        try:
            if m15_structure['signal'] == 'NONE':
                return {
                    'signal': 'NONE',
                    'reason': 'No M15 structure',
                    'confidence': 0.0
                }
            
            expected_signal = m15_structure['signal']
            confirmation_candles = self.entry_config.get('confirmation_candles', 1)
            
            # Get recent candles
            recent = df.tail(5)
            latest = df.iloc[-1]
            
            # Check for confirmation candles
            if expected_signal == 'LONG':
                # Look for bullish confirmation
                bullish_candles = 0
                for i in range(len(recent)):
                    candle = recent.iloc[i]
                    if candle['Close'] > candle['Open']:  # Bullish candle
                        bullish_candles += 1
                
                if bullish_candles >= confirmation_candles:
                    return {
                        'signal': 'LONG',
                        'pattern': m15_structure.get('pattern', 'UNKNOWN'),
                        'confidence': 0.75,
                        'details': f'{bullish_candles} bullish confirmation candles'
                    }
            
            elif expected_signal == 'SHORT':
                # Look for bearish confirmation
                bearish_candles = 0
                for i in range(len(recent)):
                    candle = recent.iloc[i]
                    if candle['Close'] < candle['Open']:  # Bearish candle
                        bearish_candles += 1
                
                if bearish_candles >= confirmation_candles:
                    return {
                        'signal': 'SHORT',
                        'pattern': m15_structure.get('pattern', 'UNKNOWN'),
                        'confidence': 0.75,
                        'details': f'{bearish_candles} bearish confirmation candles'
                    }
            
            # No clear execution signal
            return {
                'signal': 'NONE',
                'reason': 'No execution confirmation',
                'confidence': 0.0
            }
            
        except Exception as e:
            return {
                'signal': 'NONE',
                'reason': f'Error detecting execution: {e}',
                'confidence': 0.0
            }


def main():
    """Test entry engine"""
    from d1_bias_model import D1BiasModel
    from h4h1_confirmation_model import H4H1ConfirmationModel
    
    # Get D1 bias
    d1_model = D1BiasModel()
    d1_bias = d1_model.predict_bias()
    
    # Get confirmation
    conf_model = H4H1ConfirmationModel()
    confirmation = conf_model.predict_confirmation(d1_bias)
    
    # Get entry signal
    entry_engine = M15M5EntryEngine()
    entry = entry_engine.detect_entry(d1_bias, confirmation)
    
    print("\n" + "="*60)
    print("M15/M5 ENTRY ENGINE TEST")
    print("="*60)
    print(f"D1 Bias: {d1_bias['bias']}")
    print(f"Confirmation: {confirmation['confirmation']}")
    print(f"\nEntry Signal: {entry['entry_signal']}")
    print(f"Entry Type: {entry['entry_type']}")
    print(f"Confidence: {entry['confidence']:.2%}")
    if 'reason' in entry:
        print(f"Reason: {entry['reason']}")
    print("="*60)


if __name__ == "__main__":
    main()



