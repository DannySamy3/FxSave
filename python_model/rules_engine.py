"""
Trade Rules Engine (HARDENED v2.0)
Deterministic logic to filter trades based on Regime, ATR, and Confidence.

FIXES APPLIED:
- Standardized rejection codes (not full messages)
- All codes must match frontend REJECTION_MSG mapping
- Improved validation logic
"""
import json

# Standardized rejection codes - MUST match frontend REJECTION_MSG
REJECTION_CODES = {
    'LOW_CONFIDENCE': 'LOW_CONFIDENCE',
    'HTF_CONFLICT': 'HTF_CONFLICT',
    'BAD_RR': 'BAD_RR',
    'HIGH_VOLATILITY': 'HIGH_VOLATILITY',
    'RANGE_MARKET': 'RANGE_MARKET',
    'LOW_VOLATILITY': 'LOW_VOLATILITY',
    'REGIME_FILTER': 'REGIME_FILTER',
    # News-related rejection codes
    'HIGH_IMPACT_NEWS': 'HIGH_IMPACT_NEWS',
    'CALENDAR_BLACKOUT': 'CALENDAR_BLACKOUT',
    'EVENT_IMMINENT': 'EVENT_IMMINENT',
    'NEWS_NEGATIVE_SENTIMENT': 'NEWS_NEGATIVE_SENTIMENT'
}


class TradeRulesEngine:
    """
    Deterministic rules engine for trade filtering.
    All rejections use standardized codes for consistent UI display.
    """
    
    def __init__(self, config):
        self.config = config
        self.rules = config.get('rules', {})
        self.thresholds = config.get('thresholds', {})
        
    def check_trade(self, timeframe, prediction, regime_state, latest_features):
        """
        Apply NO-TRADE rules in priority order.
        
        Args:
            timeframe: Current timeframe string
            prediction: Dict with 'direction' and 'confidence' (percentage)
            regime_state: String from regime detector
            latest_features: Dict of current indicator values
            
        Returns:
            decision (str): "TRADE" or "NO_TRADE"
            reason (str): Rejection code or None
        """
        
        # Rule 1: Regime Filter (Highest Priority)
        if self.rules.get('enable_regime_filter', True):
            allowed = self.rules.get('allowed_regimes', ['STRONG_TREND', 'WEAK_TREND'])
            
            if regime_state not in allowed:
                if regime_state == "RANGE":
                    return "NO_TRADE", REJECTION_CODES['RANGE_MARKET']
                elif regime_state == "HIGH_VOLATILITY_NO_TRADE":
                    return "NO_TRADE", REJECTION_CODES['HIGH_VOLATILITY']
                elif regime_state == "UNKNOWN":
                    return "NO_TRADE", REJECTION_CODES['REGIME_FILTER']
                else:
                    return "NO_TRADE", REJECTION_CODES['REGIME_FILTER']
        
        # Rule 2: Confidence Threshold
        min_conf = self.thresholds.get('min_confidence', 0.55)
        
        # Convert percentage to decimal if needed
        conf_value = prediction.get('confidence', 0)
        conf_decimal = conf_value / 100.0 if conf_value > 1 else conf_value
        
        if conf_decimal < min_conf:
            return "NO_TRADE", REJECTION_CODES['LOW_CONFIDENCE']
        
        # Rule 3: ATR Filter (Low Volatility / Dead Market)
        if self.rules.get('block_on_low_atr', True):
            min_atr_map = self.thresholds.get('min_atr', {})
            min_atr = min_atr_map.get(timeframe, 0)
            current_atr = latest_features.get('ATR', 0)
            
            if current_atr and min_atr > 0 and current_atr < min_atr:
                return "NO_TRADE", REJECTION_CODES['LOW_VOLATILITY']
        
        # All rules passed
        return "TRADE", None
    
    def get_rejection_message(self, code):
        """
        Get human-readable message for a rejection code.
        Note: Frontend should do this mapping, but available here for logging.
        """
        messages = {
            'LOW_CONFIDENCE': 'Low Confidence Score',
            'HTF_CONFLICT': 'Higher Timeframe Conflict',
            'BAD_RR': 'Insufficient Reward/Risk Ratio',
            'HIGH_VOLATILITY': 'Extreme Volatility (News/Crash)',
            'RANGE_MARKET': 'Market in Range (No Trend)',
            'LOW_VOLATILITY': 'Low Volatility (Dead Market)',
            'REGIME_FILTER': 'Market Regime Unfavorable',
            'SL_TOO_TIGHT': 'Stop Loss Too Tight',
            'ZERO_RISK': 'Zero Risk Allocation',
            'LOT_CALC_ERROR': 'Position Size Calculation Error',
            'INSUFFICIENT_DATA': 'Insufficient Market Data',
            # News-related messages
            'HIGH_IMPACT_NEWS': 'High-Impact News Event',
            'CALENDAR_BLACKOUT': 'Economic Calendar Blackout',
            'EVENT_IMMINENT': 'Major Event Imminent',
            'NEWS_NEGATIVE_SENTIMENT': 'Strong Negative News Sentiment'
        }
        return messages.get(code, code)
    
    def get_all_rejection_codes(self):
        """Return all available rejection codes for validation"""
        return list(REJECTION_CODES.values())
