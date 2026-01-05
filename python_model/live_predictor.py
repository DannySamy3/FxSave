"""
Live Predictor Module - Rolling Predictions for Gold Trading
Generates continuous predictions as new candles complete.

Features:
- Incremental data updates (no full refetch)
- Uses cached/saved models (no retraining)
- Preserves HTF conflict rules
- Maintains calibrated confidence
- Full audit logging
"""

import pandas as pd
import numpy as np
import pickle
import json
import os
import sys
from datetime import datetime
from pathlib import Path
import warnings

# Local modules
from data_manager import DataManager, get_data_manager
from features import compute_indicators, get_feature_columns
from regime import RegimeDetector
from calibration import ModelCalibrator
from rules_engine import TradeRulesEngine
from forward_test import ForwardTester
from risk_engine import RiskManager
from news_integration import NewsIntegration, get_news_integration
from trade_decision_engine import TradeDecisionEngine

warnings.filterwarnings('ignore')


def load_config():
    """Load configuration from config.json"""
    path = Path(__file__).parent / 'config.json'
    with open(path, 'r') as f:
        return json.load(f)


class LivePredictor:
    """
    Live prediction engine for rolling Gold price predictions.
    Uses saved models and calibrators - no retraining on each call.
    """
    
    # Timeframe hierarchy for HTF validation
    TF_HIERARCHY = ['1d', '4h', '1h', '30m', '15m']
    
    # HTF parent mapping
    HTF_PARENT_MAP = {
        '15m': '30m',
        '30m': '1h',
        '1h': '4h',
        '4h': '1d',
        '1d': None
    }
    
    def __init__(self, config=None, symbol='GC=F'):
        """
        Initialize live predictor with saved models.
        
        Args:
            config: Configuration dict (loads from file if None)
            symbol: Trading symbol
        """
        self.config = config or load_config()
        self.symbol = symbol
        self.base_dir = Path(__file__).parent
        
        # Initialize components
        self.data_manager = get_data_manager(symbol)
        self.regime_detector = RegimeDetector(self.config)
        self.rules_engine = TradeRulesEngine(self.config)
        self.risk_manager = RiskManager(self.config)
        self.forward_tester = ForwardTester(
            str(self.base_dir / self.config['paths']['forward_test_log'])
        )
        
        # Load models and calibrators
        self.models = {}
        self.calibrators = {}
        self._load_artifacts()
        
        # Initialize news integration
        self.news_enabled = self.config.get('news', {}).get('enabled', False)
        if self.news_enabled:
            self.news_integration = get_news_integration(self.config)
            print("[NEWS] News integration enabled")
        else:
            self.news_integration = None
        
        # Initialize multi-timeframe decision engine (if enabled)
        self.multi_timeframe_enabled = self.config.get('multi_timeframe', {}).get('enabled', False)
        if self.multi_timeframe_enabled:
            try:
                self.decision_engine = TradeDecisionEngine(self.config)
                print("[ARCH] Multi-timeframe hierarchical architecture enabled")
            except Exception as e:
                print(f"[WARN] Failed to initialize multi-timeframe engine: {e}")
                self.multi_timeframe_enabled = False
                self.decision_engine = None
        else:
            self.decision_engine = None
        
        # Track prediction state
        self.last_predictions = {}
        self.last_news_assessment = {}
        self.prediction_count = 0
    
    def _load_artifacts(self):
        """Load all trained models and calibrators"""
        print("Loading models and calibrators...")
        
        for tf in self.TF_HIERARCHY:
            # Load model
            model_path = self.base_dir / f'xgb_{tf}.pkl'
            if model_path.exists():
                try:
                    with open(model_path, 'rb') as f:
                        self.models[tf] = pickle.load(f)
                    print(f"  [OK] Model loaded: {tf}")
                except Exception as e:
                    print(f"  [ERROR] Failed to load model {tf}: {e}")
            else:
                print(f"  [WARN] Model not found: {tf}")
            
            # Load calibrator
            calibrator = ModelCalibrator(tf)
            if calibrator.load(str(self.base_dir)):
                self.calibrators[tf] = calibrator
                print(f"  [OK] Calibrator loaded: {tf}")
            else:
                self.calibrators[tf] = calibrator  # Use uncalibrated
                print(f"  [WARN] Calibrator not found: {tf} (using uncalibrated)")
    
    def _check_htf_alignment(self, current_tf, current_direction, htf_results):
        """
        Check alignment with higher timeframes using cascading validation.
        
        Returns:
            alignment_status (str): 'ALIGNED', 'SOFT_CONFLICT', 'HARD_CONFLICT'
            alignment_details (dict): Details about the alignment check
        """
        parent_tf = self.HTF_PARENT_MAP.get(current_tf)
        
        if parent_tf is None:
            return 'ALIGNED', {'reason': 'Top-level timeframe', 'parent': None}
        
        if parent_tf not in htf_results:
            return 'ALIGNED', {'reason': f'Parent {parent_tf} not available', 'parent': parent_tf}
        
        parent_result = htf_results[parent_tf]
        parent_direction = parent_result.get('direction')
        parent_decision = parent_result.get('decision')
        parent_regime = parent_result.get('regime')
        
        # If parent decided NO_TRADE, cascade down
        if parent_decision == 'NO_TRADE':
            return 'HARD_CONFLICT', {
                'reason': f'Parent {parent_tf} is NO_TRADE',
                'parent': parent_tf,
                'parent_direction': parent_direction,
                'parent_reason': parent_result.get('rejection_reason')
            }
        
        # Check direction alignment
        if parent_direction and parent_direction != current_direction:
            if parent_regime == 'STRONG_TREND':
                return 'HARD_CONFLICT', {
                    'reason': f'Direction conflict with {parent_tf} in STRONG_TREND',
                    'parent': parent_tf,
                    'parent_direction': parent_direction,
                    'current_direction': current_direction
                }
            else:
                return 'SOFT_CONFLICT', {
                    'reason': f'Direction conflict with {parent_tf} (non-trending)',
                    'parent': parent_tf,
                    'parent_direction': parent_direction,
                    'current_direction': current_direction
                }
        
        # Check grandparent for extra safety
        grandparent_tf = self.HTF_PARENT_MAP.get(parent_tf)
        if grandparent_tf and grandparent_tf in htf_results:
            gp_result = htf_results[grandparent_tf]
            gp_direction = gp_result.get('direction')
            
            if gp_direction and gp_direction != current_direction:
                gp_regime = gp_result.get('regime')
                if gp_regime == 'STRONG_TREND':
                    return 'HARD_CONFLICT', {
                        'reason': f'Direction conflict with grandparent {grandparent_tf}',
                        'grandparent': grandparent_tf,
                        'grandparent_direction': gp_direction,
                        'current_direction': current_direction
                    }
        
        return 'ALIGNED', {
            'reason': 'Aligned with HTF',
            'parent': parent_tf,
            'parent_direction': parent_direction
        }
    
    def predict_single_timeframe(self, timeframe, htf_results=None):
        """
        Generate prediction for a single timeframe.
        
        Args:
            timeframe: Timeframe to predict
            htf_results: Results from higher timeframes for validation
            
        Returns:
            dict: Prediction result
        """
        htf_results = htf_results or {}
        feature_cols = get_feature_columns()
        
        # Check if model exists
        if timeframe not in self.models:
            return {
                'timeframe': timeframe,
                'error': 'Model not available',
                'decision': 'NO_TRADE',
                'rejection_reason': 'INSUFFICIENT_DATA'
            }
        
        # Get data (incremental update if needed)
        # Note: Increased lookback to 500 to ensure enough rows after indicator computation
        # EMA_200 needs 200 rows, TSI needs ~25 rows, so we need extra buffer after dropna()
        df = self.data_manager.get_data_for_prediction(timeframe, lookback=500)
        
        if df is None or len(df) < 50:
            return {
                'timeframe': timeframe,
                'error': f'Insufficient data ({len(df) if df is not None else 0} rows)',
                'decision': 'NO_TRADE',
                'rejection_reason': 'INSUFFICIENT_DATA'
            }
        
        # Compute indicators
        try:
            df_proc = compute_indicators(df)
        except Exception as e:
            return {
                'timeframe': timeframe,
                'error': f'Feature computation error: {str(e)}',
                'decision': 'NO_TRADE',
                'rejection_reason': 'INSUFFICIENT_DATA'
            }
        
        if df_proc is None or df_proc.empty or len(df_proc) < 10:
            return {
                'timeframe': timeframe,
                'error': f'Feature computation failed: {len(df_proc) if df_proc is not None else 0} rows after processing (need at least 10)',
                'decision': 'NO_TRADE',
                'rejection_reason': 'INSUFFICIENT_DATA'
            }
        
        latest_features = df_proc.iloc[[-1]]
        current_price = float(df_proc.iloc[-1]['Close'])
        timestamp = df_proc.index[-1].strftime('%Y-%m-%d %H:%M')
        
        # Detect regime (TF-aware)
        regime_state, regime_details = self.regime_detector.detect(df_proc, timeframe=timeframe)
        
        # Make prediction
        model = self.models[timeframe]
        X_live = latest_features[[c for c in feature_cols if c in latest_features.columns]]
        raw_prob_up = float(model.predict_proba(X_live)[0][1])
        
        raw_pred = 1 if raw_prob_up > 0.5 else 0
        direction = "UP" if raw_pred == 1 else "DOWN"
        
        # Calibrate
        calibrator = self.calibrators.get(timeframe)
        if calibrator and calibrator.is_fitted:
            calib_prob_up, has_drift_warning = calibrator.calibrate(raw_prob_up)
        else:
            calib_prob_up = raw_prob_up
            has_drift_warning = True  # Uncalibrated = warning
        
        # Calculate confidence for predicted direction
        if direction == "UP":
            raw_conf = raw_prob_up
            final_conf = calib_prob_up
        else:
            raw_conf = 1.0 - raw_prob_up
            final_conf = 1.0 - calib_prob_up
        
        final_conf_pct = round(final_conf * 100, 2)
        raw_conf_pct = round(raw_conf * 100, 2)
        calibration_drift = abs(final_conf - raw_conf)
        calibration_drift_pct = round(calibration_drift * 100, 2)
        
        # CALIBRATION DRIFT CONTROL: Evaluate drift and apply controls
        # This protects capital when model confidence reliability degrades
        drift_control_config = self.config.get('calibration_control', {})
        safe_drift = drift_control_config.get('safe_drift', 0.15)
        warning_drift = drift_control_config.get('warning_drift', 0.25)
        risk_reduction_mult = drift_control_config.get('risk_reduction_multiplier', 0.5)
        
        drift_level = None  # 'SAFE', 'WARNING', 'CRITICAL'
        drift_risk_multiplier = 1.0
        drift_rejection_reason = None
        
        if calibration_drift <= safe_drift:
            drift_level = 'SAFE'
            drift_risk_multiplier = 1.0
        elif calibration_drift <= warning_drift:
            drift_level = 'WARNING'
            drift_risk_multiplier = risk_reduction_mult
            drift_rejection_reason = 'CALIBRATION_WARNING'
        else:
            drift_level = 'CRITICAL'
            drift_risk_multiplier = 0.0
            drift_rejection_reason = 'CALIBRATION_UNSTABLE'
        
        # Check HTF alignment (cascading validation)
        htf_status, htf_details = self._check_htf_alignment(timeframe, direction, htf_results)
        
        # Rules engine check
        pred_packet = {'direction': direction, 'confidence': final_conf_pct}
        feat_dict = latest_features.iloc[0].to_dict()
        
        rules_decision, rules_reason = self.rules_engine.check_trade(
            timeframe, pred_packet, regime_state, feat_dict
        )
        
        # Determine final decision
        decision = rules_decision
        rejection_reason = rules_reason
        
        if htf_status == 'HARD_CONFLICT' and decision == 'TRADE':
            decision = 'NO_TRADE'
            rejection_reason = 'HTF_CONFLICT'
        
        # NEWS INTEGRATION: Apply news-based rules if enabled
        news_sentiment = 0.0
        news_label = 'NEUTRAL'
        news_risk_mult = 1.0
        news_headlines = []
        news_high_impact = False
        news_block_status = None
        news_event = None
        impact_level = None
        cooldown_minutes = None
        block_until = None
        
        if self.news_enabled and self.news_integration:
            news_assessment = self.news_integration.get_news_assessment(timeframe)
            self.last_news_assessment = news_assessment
            
            news_sentiment = news_assessment.get('sentiment_score', 0)
            news_label = news_assessment.get('sentiment_label', 'NEUTRAL')
            news_risk_mult = news_assessment.get('risk_multiplier', 1.0)
            news_headlines = news_assessment.get('headlines', [])[:5]
            news_high_impact = len(news_assessment.get('high_impact_events', [])) > 0
            news_block_status = news_assessment.get('news_block_status')
            
            # Extract news block details for logging
            if news_block_status:
                news_event = news_block_status.get('news_event')
                impact_level = news_block_status.get('impact_level')
                cooldown_minutes = news_block_status.get('cooldown_minutes')
                block_until = news_block_status.get('block_until')
            
            # Check if news blocks the trade (HIGH PRIORITY - overrides everything)
            if not news_assessment.get('can_trade', True):
                # Check if we're in an active cooldown period
                is_in_cooldown = news_block_status and news_block_status.get('is_blocked', False)
                
                if is_in_cooldown:
                    # Active cooldown - block trading
                    decision = 'NO_TRADE'
                    rejection_reason = 'HIGH_IMPACT_NEWS'
                    news_risk_mult = 0.0
                else:
                    # Cooldown expired - check volatility confirmation before allowing trades
                    can_trade_vol, vol_reason = self.news_integration.news_blocker.check_volatility_confirmation(
                        df_proc, timeframe
                    )
                    
                    # Also check regime (must be TREND or RANGE, not HIGH_VOLATILITY or CHAOTIC)
                    if regime_state in ['HIGH_VOLATILITY_NO_TRADE']:
                        # Still blocked - volatility not normalized
                        decision = 'NO_TRADE'
                        rejection_reason = 'HIGH_IMPACT_NEWS'
                        news_risk_mult = 0.0
                    elif not can_trade_vol:
                        # Still blocked - ATR ratio too high
                        decision = 'NO_TRADE'
                        rejection_reason = 'HIGH_IMPACT_NEWS'
                        news_risk_mult = 0.0
                    else:
                        # Volatility normalized and regime OK - allow trading to proceed
                        # (decision remains from rules engine, but we've passed the news check)
                        news_risk_mult = 1.0
            
            # Optionally adjust confidence based on sentiment (only if not blocked)
            elif decision == 'TRADE':
                final_conf = self.news_integration.adjust_confidence(
                    final_conf, direction, news_sentiment
                )
                final_conf_pct = round(final_conf * 100, 2)
        
        # CALIBRATION DRIFT CONTROL: Apply drift-based blocking/reduction
        # This overrides confidence, HTF, RR, and regime (but not news blocks)
        # Priority: News blocks > Calibration drift > Other filters
        if drift_level == 'CRITICAL':
            # CRITICAL drift - block trade (overrides everything except news)
            if decision != 'NO_TRADE' or rejection_reason != 'HIGH_IMPACT_NEWS':
                decision = 'NO_TRADE'
                rejection_reason = 'CALIBRATION_UNSTABLE'
                drift_risk_multiplier = 0.0
        
        # Risk management
        htf_risk_multiplier = 1.0
        if htf_status == 'SOFT_CONFLICT':
            htf_risk_multiplier = 0.5
        elif htf_status == 'HARD_CONFLICT':
            htf_risk_multiplier = 0.0
        
        # Apply risk multipliers in order: HTF -> News -> Calibration Drift
        combined_risk_multiplier = htf_risk_multiplier * news_risk_mult * drift_risk_multiplier
        
        # CRITICAL: If blocked by news, force risk to zero (override everything)
        if decision == 'NO_TRADE' and rejection_reason == 'HIGH_IMPACT_NEWS':
            combined_risk_multiplier = 0.0
            news_risk_mult = 0.0
        
        setup = self.risk_manager.calculate_trade_params(
            df_proc,
            direction,
            final_conf,
            htf_risk_multiplier=combined_risk_multiplier,
            regime=regime_state
        )
        
        # CRITICAL: Enforce risk=0 during blocks (override risk manager output)
        if decision == 'NO_TRADE':
            if rejection_reason == 'HIGH_IMPACT_NEWS':
                setup['risk_pct'] = 0.0
                setup['risk_amount'] = 0.0
                setup['lots'] = 0.0
                setup['decision'] = 'NO_TRADE'
                setup['reason'] = 'HIGH_IMPACT_NEWS'
            elif rejection_reason == 'CALIBRATION_UNSTABLE':
                setup['risk_pct'] = 0.0
                setup['risk_amount'] = 0.0
                setup['lots'] = 0.0
                setup['decision'] = 'NO_TRADE'
                setup['reason'] = 'CALIBRATION_UNSTABLE'
        
        # If risk manager rejects, override decision (unless already blocked by news)
        if setup.get("decision") == "NO_TRADE" and rejection_reason != 'HIGH_IMPACT_NEWS':
            if decision == "TRADE":
                decision = "NO_TRADE"
                rejection_reason = setup.get("reason", "RISK_CHECK_FAILED")
        
        # Build result
        result = {
            "timeframe": timeframe,
            "direction": direction,
            "confidence": final_conf_pct,
            "raw_confidence": raw_conf_pct,
            "calibration_drift": calibration_drift_pct,
            "calibration_warning": has_drift_warning,
            "drift_level": drift_level,
            "drift_risk_multiplier": drift_risk_multiplier,
            "decision": decision,
            "rejection_reason": rejection_reason,
            "regime": regime_state,
            "regime_details": regime_details,
            "htf_status": htf_status,
            "htf_details": htf_details,
            "current_price": round(current_price, 2),
            "timestamp": timestamp,
            "setup": setup,
            "candle_time": df_proc.index[-1].isoformat(),
            # News data
            "news": {
                "sentiment_score": round(news_sentiment, 3),
                "sentiment_label": news_label,
                "risk_multiplier": news_risk_mult,
                "high_impact": news_high_impact,
                "headlines": news_headlines,
                "block_status": news_block_status
            }
        }
        
        # Log to forward tester
        # For drift warnings (WARNING level), log CALIBRATION_WARNING in reason
        # even if decision is TRADE, to track risk reduction events for audit
        log_reason = rejection_reason
        if drift_level == 'WARNING' and decision == 'TRADE' and not rejection_reason:
            # Log drift warning even though trade is allowed (for audit trail)
            log_reason = 'CALIBRATION_WARNING'
        elif drift_rejection_reason:
            # Use drift rejection reason if set (for CRITICAL drift blocks)
            log_reason = drift_rejection_reason
        
        log_packet = {
            'symbol': self.symbol,
            'direction': direction,
            'raw_confidence': raw_conf,
            'calibrated_confidence': final_conf,
            'calibration_drift': calibration_drift,
            'drift_level': drift_level,
            'drift_rejection_reason': drift_rejection_reason,
            'regime': regime_state,
            'htf_status': htf_status,
            'htf_parent': htf_details.get('parent'),
            'decision': decision,
            'reason': log_reason,  # Includes drift warnings for audit trail
            'entry': setup.get('entry', 0),
            'sl': setup.get('sl', 0),
            'tp': setup.get('tp', 0),
            'lots': setup.get('lots', 0),
            'risk_pct': setup.get('risk_pct', 0),
            'risk_amount': setup.get('risk_amount', 0),
            'rr_ratio': setup.get('rr_ratio', 0),
            'current_price': current_price,
            # News fields (enhanced for v2.2.0)
            'news_sentiment': news_sentiment,
            'news_high_impact': news_high_impact,
            'news_headlines': '; '.join([h.get('headline', '')[:50] for h in news_headlines[:3]]),
            'news_event': news_event,
            'news_impact_level': impact_level,
            'news_cooldown_minutes': cooldown_minutes,
            'news_block_until': block_until,
            # TTL logging fields (enhanced for true recency validation)
            'news_present': news_assessment.get('news_present', False) if self.news_enabled else False,
            'news_age_minutes': news_assessment.get('news_age_minutes') if self.news_enabled else None,
            'news_impact': news_assessment.get('news_impact') if self.news_enabled else None,
            'news_cache_cleared': news_assessment.get('news_cache_cleared', False) if self.news_enabled else False,
            'trade_blocked_by_news': news_assessment.get('trade_blocked_by_news', False) if self.news_enabled else False,
            'news_classification': news_assessment.get('news_classification', 'UNVERIFIED') if self.news_enabled else None,
            'news_origin_timestamp': news_assessment.get('news_origin_timestamp') if self.news_enabled else None,
            'news_fetch_timestamp': news_assessment.get('news_fetch_timestamp') if self.news_enabled else None,
            'cache_age_minutes': news_assessment.get('cache_age_minutes') if self.news_enabled else None
        }
        self.forward_tester.log_signal(timeframe, log_packet)
        
        return result
    
    def predict_all_timeframes(self, update_data=True):
        """
        Generate predictions for all timeframes with HTF validation.
        
        Args:
            update_data: Whether to fetch new data first
            
        Returns:
            dict: All predictions keyed by timeframe
        """
        print("\n" + "=" * 60)
        print(f"LIVE PREDICTION - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        # Update data if requested
        if update_data:
            print("\n[UPDATE] Updating market data...")
            update_results = self.data_manager.update_all_timeframes()
            for tf, count in update_results.items():
                status = f"+{count}" if count > 0 else "up-to-date" if count == 0 else "error"
                print(f"  {tf}: {status}")
        
        # Generate predictions in hierarchical order
        results = {}
        
        for tf in self.TF_HIERARCHY:
            print(f"\n{'-' * 40}")
            print(f"Processing {tf}...")
            
            result = self.predict_single_timeframe(tf, htf_results=results)
            results[tf] = result
            
            # Print summary
            if result.get('error'):
                print(f"  [ERROR] Error: {result['error']}")
            else:
                icon = "[TRADE]" if result['decision'] == 'TRADE' else "[BLOCK]"
                print(f"  Direction: {result['direction']} | Conf: {result['confidence']}%")
                print(f"  Regime: {result['regime']} | HTF: {result['htf_status']}")
                print(f"  {icon} Decision: {result['decision']}")
                if result['decision'] == 'NO_TRADE':
                    print(f"     Reason: {result['rejection_reason']}")
                else:
                    setup = result['setup']
                    print(f"     Lots: {setup.get('lots')} | RR: 1:{setup.get('rr_ratio')}")
        
        # Store last predictions
        self.last_predictions = results
        self.prediction_count += 1
        
        # Save to JSON
        self._save_predictions(results)
        
        return results
    
    def predict_hierarchical(self, update_data=True):
        """
        Generate prediction using multi-timeframe hierarchical architecture.
        
        Uses:
        - D1 Bias Model (permission layer)
        - H4/H1 Confirmation Model (confirmation layer)
        - M15/M5 Entry Engine (execution layer)
        - Confidence Gate (validation layer)
        - Trade Decision Engine (final arbiter)
        
        Args:
            update_data: Whether to fetch new data first
            
        Returns:
            dict: Hierarchical decision result
        """
        if not self.multi_timeframe_enabled or self.decision_engine is None:
            print("[WARN] Multi-timeframe architecture not enabled, falling back to standard prediction")
            return self.predict_all_timeframes(update_data=update_data)
        
        print("\n" + "=" * 70)
        print(f"HIERARCHICAL PREDICTION - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        # Update data if requested
        if update_data:
            print("\n[UPDATE] Updating market data...")
            update_results = self.data_manager.update_all_timeframes()
            for tf, count in update_results.items():
                status = f"+{count}" if count > 0 else "up-to-date" if count == 0 else "error"
                print(f"  {tf}: {status}")
        
        # Get hierarchical decision
        print("\n[DECISION] Running hierarchical decision flow...")
        decision = self.decision_engine.make_decision(update_data=False)
        
        # Format result for compatibility with existing system
        result = {
            'hierarchical': True,
            'decision': decision['decision'],
            'direction': decision['direction'],
            'confidence': decision['confidence'],
            'reason': decision['reason'],
            'layers': decision['layers'],
            'timestamp': decision['timestamp']
        }
        
        # Print summary
        print("\n" + self.decision_engine.get_decision_summary(decision))
        
        # Store last prediction
        self.last_predictions = {'hierarchical': result}
        self.prediction_count += 1
        
        # Save to JSON (format for frontend compatibility)
        self._save_hierarchical_prediction(result)
        
        return result
    
    def _save_hierarchical_prediction(self, result):
        """Save hierarchical prediction to JSON file"""
        out_path = self.base_dir / self.config['paths']['predictions_file']
        out_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Format for frontend compatibility
        output = {
            'timestamp': result['timestamp'],
            'hierarchical': True,
            'decision': result['decision'],
            'direction': result['direction'],
            'confidence': result['confidence'],
            'reason': result['reason'],
            'layers': {
                'd1_bias': result['layers'].get('d1_bias', {}),
                'h4h1_confirmation': result['layers'].get('h4h1_confirmation', {}),
                'entry_signal': result['layers'].get('entry_signal', {}),
                'confidence_gate': result['layers'].get('confidence_gate', {})
            }
        }
        
        with open(out_path, 'w') as f:
            json.dump(output, f, indent=2, default=str)
        
        print(f"\n[SAVED] Prediction saved to {out_path}")
    
    def _save_predictions(self, results):
        """Save predictions to JSON file for frontend"""
        out_path = self.base_dir / self.config['paths']['predictions_file']
        
        # Build news summary if enabled
        news_summary = None
        if self.news_enabled and self.last_news_assessment:
            news_summary = {
                'sentiment_score': self.last_news_assessment.get('sentiment_score', 0),
                'sentiment_label': self.last_news_assessment.get('sentiment_label', 'NEUTRAL'),
                'bullish_count': self.last_news_assessment.get('bullish_count', 0),
                'bearish_count': self.last_news_assessment.get('bearish_count', 0),
                'neutral_count': self.last_news_assessment.get('neutral_count', 0),
                'high_impact_events': self.last_news_assessment.get('high_impact_events', []),
                'upcoming_events': self.last_news_assessment.get('upcoming_events', []),
                'headlines': self.last_news_assessment.get('headlines', [])[:10],
                'can_trade': self.last_news_assessment.get('can_trade', True),
                'block_reason': self.last_news_assessment.get('reason')
            }
        
        output = {
            "generated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC'),
            "system_version": self.config['system']['version'],
            "mode": "live",
            "prediction_count": self.prediction_count,
            "predictions": results,
            "news": news_summary
        }
        
        try:
            with open(out_path, 'w') as f:
                json.dump(output, f, indent=2, default=str)
            print(f"\n[SAVED] Saved to {out_path}")
        except Exception as e:
            print(f"\n[ERROR] Error saving: {e}")
        
        # Also save news state separately for UI
        if self.news_enabled and self.news_integration:
            self.news_integration.save_news_state(str(self.base_dir))
    
    def get_status(self):
        """Get current predictor status"""
        status = {
            "models_loaded": list(self.models.keys()),
            "calibrators_loaded": [tf for tf, c in self.calibrators.items() if c.is_fitted],
            "prediction_count": self.prediction_count,
            "last_prediction_time": self.last_predictions.get('1h', {}).get('timestamp'),
            "data_status": self.data_manager.get_update_status(),
            "news_enabled": self.news_enabled
        }
        
        if self.news_enabled and self.last_news_assessment:
            status["news_status"] = {
                "sentiment": self.last_news_assessment.get('sentiment_label', 'UNKNOWN'),
                "can_trade": self.last_news_assessment.get('can_trade', True),
                "high_impact_count": len(self.last_news_assessment.get('high_impact_events', []))
            }
        
        return status
    
    def predict_if_new_candle(self, timeframe):
        """
        Only predict if there's a new candle (avoids duplicate predictions).
        
        Returns:
            dict or None: Prediction if new candle, None otherwise
        """
        # Check if we need an update
        if not self.data_manager.needs_update(timeframe):
            return None
        
        # Fetch new data
        _, new_rows = self.data_manager.fetch_incremental_update(timeframe)
        
        if new_rows == 0:
            return None
        
        # New candle detected - generate prediction
        print(f"🆕 New candle detected for {timeframe}")
        return self.predict_single_timeframe(timeframe, htf_results=self.last_predictions)


def run_live_prediction():
    """Run a single live prediction cycle"""
    predictor = LivePredictor()
    results = predictor.predict_all_timeframes(update_data=True)
    
    print("\n" + "=" * 60)
    print("PREDICTION SUMMARY")
    print("=" * 60)
    
    for tf in LivePredictor.TF_HIERARCHY:
        if tf in results:
            r = results[tf]
            if r.get('error'):
                print(f"{tf:5s} | [ERROR] {r['error']}")
            else:
                icon = "✅" if r['decision'] == 'TRADE' else "⛔"
                print(f"{tf:5s} | {r['direction']:4s} | {r['confidence']:5.1f}% | "
                      f"{r['regime']:15s} | {icon} {r['decision']}")
    
    return results


if __name__ == "__main__":
    import argparse
    import time
    from datetime import datetime, timedelta
    
    parser = argparse.ArgumentParser(
        description='Live Gold Price Prediction Engine',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python live_predictor.py                    # Single prediction cycle
  python live_predictor.py --paper_trade      # Paper trading mode (continuous)
  python live_predictor.py --paper_trade --duration 24h  # 24-hour paper trading
  python live_predictor.py --once             # Single prediction, then exit
        """
    )
    
    parser.add_argument('--paper_trade', action='store_true',
                        help='Enable paper trading mode (continuous predictions)')
    parser.add_argument('--duration', type=str, default='24h',
                        help='Paper trading duration (e.g., 24h, 7d). Default: 24h')
    parser.add_argument('--once', action='store_true',
                        help='Run single prediction cycle, then exit')
    parser.add_argument('--interval', type=int, default=300,
                        help='Prediction interval in seconds (default: 300 = 5 min)')
    
    args = parser.parse_args()
    
    if args.paper_trade:
        # Parse duration
        duration_str = args.duration.lower()
        if duration_str.endswith('h'):
            hours = int(duration_str[:-1])
        elif duration_str.endswith('d'):
            hours = int(duration_str[:-1]) * 24
        else:
            hours = 24  # Default
        
        end_time = datetime.now() + timedelta(hours=hours)
        
        print("=" * 60)
        print("PAPER TRADING MODE")
        print("=" * 60)
        print(f"Duration: {hours} hours")
        print(f"End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Interval: {args.interval} seconds")
        print("=" * 60)
        print("\nPress Ctrl+C to stop early\n")
        
        predictor = LivePredictor()
        cycle = 0
        
        try:
            while datetime.now() < end_time:
                cycle += 1
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Cycle {cycle}")
                print("-" * 60)
                
                results = predictor.predict_all_timeframes(update_data=True)
                
                # Summary
                trades = sum(1 for r in results.values() if r.get('decision') == 'TRADE')
                no_trades = len(results) - trades
                print(f"\nSummary: {trades} TRADE, {no_trades} NO_TRADE")
                
                # Wait for next cycle
                if datetime.now() < end_time:
                    sleep_time = min(args.interval, (end_time - datetime.now()).total_seconds())
                    if sleep_time > 0:
                        print(f"\nSleeping {sleep_time:.0f} seconds until next cycle...")
                        time.sleep(sleep_time)
            
            print("\n" + "=" * 60)
            print(f"Paper trading completed after {hours} hours ({cycle} cycles)")
            print("=" * 60)
            
        except KeyboardInterrupt:
            print("\n\n" + "=" * 60)
            print(f"Paper trading stopped by user after {cycle} cycles")
            print("=" * 60)
    
    elif args.once:
        # Single prediction
        run_live_prediction()
    else:
        # Default: single prediction
        run_live_prediction()

