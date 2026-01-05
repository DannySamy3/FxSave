"""
Risk Management & Position Sizing Engine (HARDENED v2.0)
Handles Lot Calculation, SL/TP Placement, and Trade Validation for XAUUSD.

FIXES APPLIED:
- Standardized rejection codes (not full messages)
- HTF risk multiplier integration
- Dynamic balance support via callback
- Improved lot calculation validation
- Better error handling
"""
import math
import os
import json

# Standardized rejection codes - must match frontend REJECTION_MSG
REJECTION_CODES = {
    'SL_TOO_TIGHT': 'SL_TOO_TIGHT',
    'BAD_RR': 'BAD_RR',
    'HTF_CONFLICT': 'HTF_CONFLICT',
    'ZERO_RISK': 'ZERO_RISK',
    'LOT_CALC_ERROR': 'LOT_CALC_ERROR',
    'INSUFFICIENT_DATA': 'INSUFFICIENT_DATA'
}


class RiskManager:
    """
    Risk Management Engine for XAUUSD trading.
    Calculates position sizes, SL/TP levels, and validates risk parameters.
    """
    
    def __init__(self, config, balance_callback=None):
        """
        Args:
            config: Configuration dictionary
            balance_callback: Optional callable that returns current account balance.
                              If None, uses static config value.
        """
        self.config = config
        self.risk_cfg = config.get('risk_management', {})
        self.xau_cfg = self.risk_cfg.get('xauusd', {})
        self.balance_callback = balance_callback
        
    def get_account_balance(self):
        """
        Get current account balance.
        Uses dynamic callback if available, otherwise falls back to config.
        """
        if self.balance_callback and callable(self.balance_callback):
            try:
                balance = self.balance_callback()
                if balance and balance > 0:
                    return float(balance)
            except Exception as e:
                print(f"  ⚠️ Balance callback failed: {e}")
        
        # Fallback to config
        return float(self.risk_cfg.get('account_balance', 10000))
    
    def set_balance_callback(self, callback):
        """Set a dynamic balance callback function"""
        self.balance_callback = callback
        
    def calculate_trade_params(self, df, direction, confidence, htf_risk_multiplier=1.0, regime="UNKNOWN"):
        """
        Main entry point for calculating trade parameters.
        
        Args:
            df: DataFrame with price data and indicators
            direction: "UP" or "DOWN"
            confidence: Calibrated confidence (0.0-1.0)
            htf_risk_multiplier: Risk multiplier from HTF alignment (0.0-1.0)
            regime: Market regime string
            
        Returns:
            Dict with trade parameters or rejection reason
        """
        try:
            # Validate input
            if df is None or len(df) < 5:
                return {
                    "decision": "NO_TRADE",
                    "reason": REJECTION_CODES['INSUFFICIENT_DATA']
                }
            
            latest = df.iloc[-1]
            entry_price = float(latest['Close'])
            
            # Get ATR for volatility-based calculations
            if 'ATR' in df.columns and not math.isnan(latest['ATR']):
                atr = float(latest['ATR'])
            else:
                # Fallback: Use recent range as ATR proxy
                atr = float(df['High'].iloc[-5:].max() - df['Low'].iloc[-5:].min()) / 2
            
            # 1. Calculate SL and TP Levels (volatility-aware)
            sl_price, tp_price = self._calculate_levels(df, direction, entry_price, atr, regime)
            
            # 2. Validate Stop Distance
            sl_dist = abs(entry_price - sl_price)
            
            # Minimum stop distance: $0.50 for XAUUSD (50 pips)
            min_sl_dist = 0.5
            if sl_dist < min_sl_dist:
                return {
                    "decision": "NO_TRADE",
                    "reason": REJECTION_CODES['SL_TOO_TIGHT'],
                    "sl_dist_actual": round(sl_dist, 2),
                    "sl_dist_required": min_sl_dist
                }
            
            # 3. Calculate Risk Reward
            potential_loss = sl_dist
            potential_gain = abs(tp_price - entry_price)
            rr_ratio = potential_gain / potential_loss if potential_loss > 0 else 0
            
            # 4. Validate RR (Minimum 1:2)
            min_rr = self.risk_cfg.get('min_rr_ratio', 2.0)
            
            if rr_ratio < min_rr:
                return {
                    "decision": "NO_TRADE",
                    "reason": REJECTION_CODES['BAD_RR'],
                    "rr_actual": round(rr_ratio, 2),
                    "rr_required": min_rr
                }
            
            # 5. Check HTF Risk Multiplier
            if htf_risk_multiplier <= 0:
                return {
                    "decision": "NO_TRADE",
                    "reason": REJECTION_CODES['HTF_CONFLICT'],
                    "htf_multiplier": htf_risk_multiplier
                }
            
            # 6. Calculate Position Risk %
            base_risk_pct = self._get_base_risk(confidence, regime)
            final_risk_pct = base_risk_pct * htf_risk_multiplier
            
            # Apply max risk cap
            max_risk = self.risk_cfg.get('max_risk_pct', 2.0)
            final_risk_pct = min(final_risk_pct, max_risk)
            
            if final_risk_pct <= 0:
                return {
                    "decision": "NO_TRADE",
                    "reason": REJECTION_CODES['ZERO_RISK']
                }
            
            # 7. Calculate Lot Size
            account_bal = self.get_account_balance()
            risk_amount = account_bal * (final_risk_pct / 100.0)
            
            lots = self._calculate_lots(risk_amount, sl_dist)
            
            if lots <= 0:
                return {
                    "decision": "NO_TRADE",
                    "reason": REJECTION_CODES['LOT_CALC_ERROR'],
                    "risk_amount": round(risk_amount, 2),
                    "sl_dist": round(sl_dist, 2)
                }
            
            return {
                "decision": "TRADE",
                "entry": round(entry_price, 2),
                "sl": round(sl_price, 2),
                "tp": round(tp_price, 2),
                "lots": lots,
                "risk_amount": round(risk_amount, 2),
                "risk_pct": round(final_risk_pct, 2),
                "base_risk_pct": round(base_risk_pct, 2),
                "htf_multiplier": htf_risk_multiplier,
                "rr_ratio": round(rr_ratio, 2),
                "stop_distance": round(sl_dist, 2),
                "account_balance": round(account_bal, 2)
            }
            
        except Exception as e:
            return {
                "decision": "NO_TRADE",
                "reason": REJECTION_CODES['LOT_CALC_ERROR'],
                "error": str(e)
            }
        
    def _calculate_levels(self, df, direction, entry, atr, regime):
        """
        Calculate SL/TP levels using swing structure + ATR.
        
        SL: Behind recent swing (with ATR buffer)
        TP: Multiple of risk distance, extended in strong trends
        """
        # Lookback for swing detection
        lookback = min(10, len(df) - 1)
        recent_high = float(df['High'].iloc[-lookback:].max())
        recent_low = float(df['Low'].iloc[-lookback:].min())
        
        # ATR buffer to avoid stop hunting
        atr_buffer = atr * 0.3
        
        if direction == "UP":
            # SL: Below recent swing low
            structure_sl = recent_low - atr_buffer
            
            # ATR-based fallback
            volatility_sl = entry - (atr * 1.5)
            
            # Use the one that gives reasonable room
            if structure_sl >= entry:
                # Invalid structure SL, use volatility
                sl_price = volatility_sl
            else:
                # Use wider of the two for safety
                sl_price = min(structure_sl, volatility_sl)
            
            # Sanity check: SL not more than 5% of price
            max_sl_dist = entry * 0.05
            if entry - sl_price > max_sl_dist:
                sl_price = entry - (atr * 1.5)
            
            risk_dist = entry - sl_price
            
            # TP Calculation
            reward_mult = 2.0  # Default 1:2
            if regime == "STRONG_TREND":
                reward_mult = 3.0  # Let winners run in strong trend
            
            tp_price = entry + (risk_dist * reward_mult)
            
        else:  # DOWN
            # SL: Above recent swing high
            structure_sl = recent_high + atr_buffer
            volatility_sl = entry + (atr * 1.5)
            
            if structure_sl <= entry:
                sl_price = volatility_sl
            else:
                sl_price = max(structure_sl, volatility_sl)
            
            # Sanity check
            max_sl_dist = entry * 0.05
            if sl_price - entry > max_sl_dist:
                sl_price = entry + (atr * 1.5)
            
            risk_dist = sl_price - entry
            
            reward_mult = 2.0
            if regime == "STRONG_TREND":
                reward_mult = 3.0
            
            tp_price = entry - (risk_dist * reward_mult)
        
        return sl_price, tp_price
    
    def _get_base_risk(self, confidence, regime):
        """
        Determine base risk percentage based on confidence and regime.
        
        Higher confidence = potentially slightly higher risk (within limits)
        Range markets = reduced risk
        """
        base_risk = self.risk_cfg.get('base_risk_pct', 1.0)
        
        # Regime adjustment
        regime_mult = {
            'STRONG_TREND': 1.0,
            'WEAK_TREND': 0.8,
            'RANGE': 0.5,
            'HIGH_VOLATILITY_NO_TRADE': 0.0,
            'UNKNOWN': 0.5
        }
        
        regime_factor = regime_mult.get(regime, 0.5)
        
        # Confidence adjustment (subtle)
        # Only boost risk slightly for very high confidence
        conf_factor = 1.0
        if confidence > 0.75:
            conf_factor = 1.1  # 10% boost for high confidence
        elif confidence < 0.55:
            conf_factor = 0.8  # 20% reduction for low confidence
        
        final_risk = base_risk * regime_factor * conf_factor
        
        return final_risk

    def _calculate_lots(self, risk_usd, stop_distance_price):
        """
        Calculate lot size for XAUUSD.
        
        Formula: Lots = Risk_USD / (Stop_Distance * Contract_Size)
        
        For XAUUSD:
        - 1 standard lot = 100 oz
        - 1 pip = $0.01 per oz
        - P&L per lot = Price_Change * 100
        """
        contract_size = self.xau_cfg.get('contract_size', 100)
        min_lot = self.xau_cfg.get('min_lot', 0.01)
        max_lot = self.xau_cfg.get('max_lot', 10.0)
        lot_step = self.xau_cfg.get('lot_step', 0.01)
        
        if stop_distance_price <= 0:
            return 0
        
        if risk_usd <= 0:
            return 0
        
        # Calculate raw lots
        raw_lots = risk_usd / (stop_distance_price * contract_size)
        
        # Round down to lot step
        lots = math.floor(raw_lots / lot_step) * lot_step
        
        # Apply limits
        if lots < min_lot:
            # Risk too small for minimum lot
            return 0
        
        if lots > max_lot:
            lots = max_lot
        
        return round(lots, 2)
    
    def validate_trade_params(self, setup):
        """
        Validate a trade setup dictionary.
        Returns (is_valid, issues_list)
        """
        issues = []
        
        if not setup:
            return False, ["Setup is empty"]
        
        if setup.get('decision') != 'TRADE':
            return False, [f"Decision is {setup.get('decision')}"]
        
        # Required fields
        required = ['entry', 'sl', 'tp', 'lots', 'rr_ratio']
        for field in required:
            if field not in setup or setup[field] is None:
                issues.append(f"Missing {field}")
        
        if issues:
            return False, issues
        
        # Validate values
        if setup['lots'] <= 0:
            issues.append("Lots must be positive")
        
        if setup['rr_ratio'] < 1:
            issues.append("RR ratio must be >= 1")
        
        # SL/TP direction check
        entry = setup['entry']
        sl = setup['sl']
        tp = setup['tp']
        
        # Infer direction
        if tp > entry:
            # Long
            if sl >= entry:
                issues.append("SL must be below entry for long")
        else:
            # Short
            if sl <= entry:
                issues.append("SL must be above entry for short")
        
        return len(issues) == 0, issues
