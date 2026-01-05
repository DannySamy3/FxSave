"""
Market Regime Detection Module (HARDENED v2.0)
Classifies market state into: STRONG_TREND, WEAK_TREND, RANGE, HIGH_VOLATILITY_NO_TRADE

FIXES APPLIED:
- Timeframe-aware ADX/ATR thresholds
- Independent from ML predictions (purely technical)
- Added regime confidence scoring
- Improved edge case handling
"""
import pandas as pd
import numpy as np

# Timeframe-aware thresholds
# Higher timeframes typically need lower ADX to signal a trend
TF_THRESHOLDS = {
    '15m': {
        'adx_strong': 45,      # ADX > 45 = strong trend on 15m
        'adx_weak': 30,        # ADX > 30 = weak trend on 15m
        'atr_spike': 3.0,      # ATR ratio > 3.0 = extreme volatility
        'bbw_squeeze': 15,     # BBW percentile < 15 = squeeze
    },
    '30m': {
        'adx_strong': 42,
        'adx_weak': 28,
        'atr_spike': 2.8,
        'bbw_squeeze': 18,
    },
    '1h': {
        'adx_strong': 40,
        'adx_weak': 25,
        'atr_spike': 2.5,
        'bbw_squeeze': 20,
    },
    '4h': {
        'adx_strong': 35,
        'adx_weak': 22,
        'atr_spike': 2.3,
        'bbw_squeeze': 22,
    },
    '1d': {
        'adx_strong': 30,      # On daily, ADX > 30 is already strong
        'adx_weak': 20,
        'atr_spike': 2.0,
        'bbw_squeeze': 25,
    },
}

# Default thresholds if timeframe not specified
DEFAULT_THRESHOLDS = {
    'adx_strong': 40,
    'adx_weak': 25,
    'atr_spike': 2.5,
    'bbw_squeeze': 20,
}


class RegimeDetector:
    """
    Market Regime Detection - INDEPENDENT from ML predictions.
    Uses only technical indicators: ADX, ATR, Bollinger Bands.
    """
    
    def __init__(self, config=None):
        self.config = config or {}
        
    def detect(self, df, timeframe=None):
        """
        Analyze dataframe and return regime state + details.
        
        Args:
            df: DataFrame with computed indicators (ADX, ATR, BB_Width)
            timeframe: Optional timeframe string for TF-aware thresholds
            
        Returns:
            regime_state (str): STRONG_TREND, WEAK_TREND, RANGE, HIGH_VOLATILITY_NO_TRADE, UNKNOWN
            regime_details (dict): Details about the classification
        """
        # Get timeframe-specific thresholds
        thresholds = TF_THRESHOLDS.get(timeframe, DEFAULT_THRESHOLDS)
        
        # Minimum data check
        if len(df) < 50:
            return "UNKNOWN", {
                "reason": f"Insufficient data ({len(df)} < 50 rows)",
                "adx": None,
                "bbw_pct": None,
                "atr_ratio": None,
                "timeframe": timeframe
            }
        
        try:
            latest = df.iloc[-1]
            
            # 1. ADX Analysis (Trend Strength)
            adx = float(latest['ADX']) if 'ADX' in df.columns and pd.notna(latest['ADX']) else None
            
            # 2. Volatility Analysis (BB Width Percentile)
            if 'BB_Width' in df.columns and pd.notna(latest['BB_Width']):
                recent_bbw = df['BB_Width'].iloc[-50:].dropna()
                if len(recent_bbw) > 10:
                    current_bbw = float(latest['BB_Width'])
                    bbw_percentile = float((recent_bbw < current_bbw).mean() * 100)
                else:
                    bbw_percentile = 50.0
            else:
                bbw_percentile = 50.0
                
            # 3. ATR Analysis (Extreme Volatility)
            if 'ATR' in df.columns and pd.notna(latest['ATR']):
                atr = float(latest['ATR'])
                recent_atr = df['ATR'].iloc[-50:].dropna()
                if len(recent_atr) > 10:
                    avg_atr = float(recent_atr.mean())
                    atr_ratio = atr / avg_atr if avg_atr > 0 else 1.0
                else:
                    atr_ratio = 1.0
            else:
                atr_ratio = 1.0
                atr = None
            
            # 4. Trend direction from EMAs (for context)
            trend_direction = self._get_trend_direction(df)
            
            # --- Classification Logic (using TF-aware thresholds) ---
            
            regime_details = {
                "adx": round(adx, 1) if adx else None,
                "bbw_pct": round(bbw_percentile, 1),
                "atr_ratio": round(atr_ratio, 2),
                "timeframe": timeframe,
                "thresholds_used": thresholds,
                "trend_direction": trend_direction
            }
            
            # CRITICAL: High Impact / Crash mode
            if atr_ratio > thresholds['atr_spike']:
                regime_details["reason"] = f"Extreme Volatility (ATR ratio {atr_ratio:.1f}x > {thresholds['atr_spike']}x)"
                return "HIGH_VOLATILITY_NO_TRADE", regime_details
            
            # ADX-based classification
            if adx is not None:
                if adx > thresholds['adx_strong']:
                    regime_details["reason"] = f"Strong Trend (ADX {adx:.1f} > {thresholds['adx_strong']})"
                    return "STRONG_TREND", regime_details
                    
                if adx > thresholds['adx_weak']:
                    regime_details["reason"] = f"Weak Trend (ADX {adx:.1f} > {thresholds['adx_weak']})"
                    return "WEAK_TREND", regime_details
            
            # Ranging (Low ADX)
            # Check for Squeeze (Low BB Width) - potential breakout
            if bbw_percentile < thresholds['bbw_squeeze']:
                regime_details["reason"] = f"Range + BB Squeeze (BBW percentile {bbw_percentile:.0f}% < {thresholds['bbw_squeeze']}%)"
                return "RANGE", regime_details
            
            # Default: Range
            regime_details["reason"] = f"Range Market (ADX {adx:.1f if adx else 'N/A'} < {thresholds['adx_weak']})"
            return "RANGE", regime_details
            
        except Exception as e:
            return "UNKNOWN", {
                "reason": f"Detection error: {str(e)}",
                "timeframe": timeframe
            }
    
    def _get_trend_direction(self, df):
        """
        Determine trend direction from EMAs.
        Returns: 'BULLISH', 'BEARISH', or 'NEUTRAL'
        """
        try:
            latest = df.iloc[-1]
            
            # Check EMA alignment
            if 'EMA_10' in df.columns and 'EMA_50' in df.columns:
                ema_10 = latest['EMA_10']
                ema_50 = latest['EMA_50']
                close = latest['Close']
                
                if pd.notna(ema_10) and pd.notna(ema_50):
                    # Bullish: Price > EMA10 > EMA50
                    if close > ema_10 > ema_50:
                        return "BULLISH"
                    # Bearish: Price < EMA10 < EMA50
                    elif close < ema_10 < ema_50:
                        return "BEARISH"
            
            return "NEUTRAL"
            
        except:
            return "NEUTRAL"
    
    def get_regime_score(self, regime_state):
        """
        Return a numeric score for regime quality.
        Higher score = better conditions for trading.
        """
        scores = {
            'STRONG_TREND': 100,
            'WEAK_TREND': 70,
            'RANGE': 30,
            'HIGH_VOLATILITY_NO_TRADE': 0,
            'UNKNOWN': 0
        }
        return scores.get(regime_state, 0)
    
    def is_tradeable_regime(self, regime_state, allowed_regimes=None):
        """
        Check if regime allows trading.
        """
        if allowed_regimes is None:
            allowed_regimes = ['STRONG_TREND', 'WEAK_TREND']
        
        return regime_state in allowed_regimes
