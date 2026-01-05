"""
Gold (XAUUSD) Hardened Prediction Engine v2.1
Integrates: Regime Detection, Calibration, Rules Engine, Forward Testing, Risk Management.

Supports two modes:
1. BATCH MODE: Full data fetch and prediction (default, for manual runs)
2. LIVE MODE: Incremental updates using cached data (for scheduled runs)

FIXES APPLIED:
- Cascading HTF validation (1D→4H→1H→30m→15m)
- Proper HTF bias usage for all timeframes
- Standardized rejection codes
- Improved error handling and logging
- Calibration drift warnings
- Incremental data support
"""

import pandas as pd
import numpy as np
import yfinance as yf
import pickle
import json
import os
import sys
import warnings
import argparse
from datetime import datetime

# Modules
from features import compute_indicators, get_feature_columns
from regime import RegimeDetector
from calibration import ModelCalibrator
from rules_engine import TradeRulesEngine
from forward_test import ForwardTester
from risk_engine import RiskManager
from news_integration import NewsIntegration, get_news_integration

warnings.filterwarnings('ignore')


def load_config():
    path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(path, 'r') as f:
        return json.load(f)


CONFIG = load_config()

# Prediction mode
PREDICTION_MODE = 'batch'  # 'batch' or 'live'

# Cascading HTF hierarchy (processed in this order)
# 1D validates 4H, 4H validates 1H, 1H validates 30m, 30m validates 15m
TIMEFRAME_HIERARCHY = ['1d', '4h', '1h', '30m', '15m']

# HTF parent mapping for validation
HTF_PARENT_MAP = {
    '15m': '30m',    # 15m validated by 30m
    '30m': '1h',     # 30m validated by 1h
    '1h': '4h',      # 1h validated by 4h
    '4h': '1d',      # 4h validated by 1d
    '1d': None       # 1d has no parent
}

TIMEFRAMES = {
    '15m': {'period': '1mo', 'interval': '15m'},
    '30m': {'period': '1mo', 'interval': '30m'},
    '1h':  {'period': '60d', 'interval': '1h'},
    '4h':  {'period': '60d', 'interval': '1h'},
    '1d':  {'period': '2y',  'interval': '1d'}
}


def load_artifacts(timeframe):
    """Load model and calibrator for a timeframe with validation"""
    base_dir = os.path.dirname(__file__)
    
    # Model
    m_path = os.path.join(base_dir, f'xgb_{timeframe}.pkl')
    if not os.path.exists(m_path):
        print(f"  ⚠️ Model not found: {m_path}")
        return None, None
        
    try:
        with open(m_path, 'rb') as f:
            model = pickle.load(f)
    except Exception as e:
        print(f"  ❌ Failed to load model {timeframe}: {e}")
        return None, None
    
    # Calibrator
    calibrator = ModelCalibrator(timeframe)
    loaded = calibrator.load(base_dir)
    
    if not loaded:
        print(f"  ⚠️ Calibrator not loaded for {timeframe} - using uncalibrated probs")
    
    return model, calibrator


def get_data(timeframe):
    """Download latest data for a timeframe"""
    cfg = TIMEFRAMES[timeframe]
    try:
        df = yf.download('GC=F', period=cfg['period'], interval=cfg['interval'], progress=False)
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        if timeframe == '4h':
            logic = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
            logic = {k: v for k, v in logic.items() if k in df.columns}
            df = df.resample('4h').agg(logic).dropna()
            
        return df
        
    except Exception as e:
        print(f"  ❌ Error downloading {timeframe}: {e}")
        return pd.DataFrame()


def check_htf_alignment(current_tf, current_direction, htf_results):
    """
    Check alignment with higher timeframes using cascading validation.
    
    Returns:
        alignment_status (str): 'ALIGNED', 'SOFT_CONFLICT', 'HARD_CONFLICT'
        alignment_details (dict): Details about the alignment check
    """
    parent_tf = HTF_PARENT_MAP.get(current_tf)
    
    if parent_tf is None:
        # Top-level timeframe (1D) - always aligned
        return 'ALIGNED', {'reason': 'Top-level timeframe', 'parent': None}
    
    if parent_tf not in htf_results:
        # Parent not processed yet - should not happen with proper ordering
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
        # Directions conflict
        if parent_regime in ['STRONG_TREND']:
            # Hard conflict in strong trend
            return 'HARD_CONFLICT', {
                'reason': f'Direction conflict with {parent_tf} in STRONG_TREND',
                'parent': parent_tf,
                'parent_direction': parent_direction,
                'current_direction': current_direction
            }
        else:
            # Soft conflict - reduce risk but allow trade
            return 'SOFT_CONFLICT', {
                'reason': f'Direction conflict with {parent_tf} (non-trending)',
                'parent': parent_tf,
                'parent_direction': parent_direction,
                'current_direction': current_direction
            }
    
    # Also check grandparent for extra safety (e.g., 15m checks both 30m and 1h)
    grandparent_tf = HTF_PARENT_MAP.get(parent_tf)
    if grandparent_tf and grandparent_tf in htf_results:
        gp_result = htf_results[grandparent_tf]
        gp_direction = gp_result.get('direction')
        
        if gp_direction and gp_direction != current_direction:
            gp_regime = gp_result.get('regime')
            if gp_regime == 'STRONG_TREND':
                return 'HARD_CONFLICT', {
                    'reason': f'Direction conflict with grandparent {grandparent_tf} in STRONG_TREND',
                    'grandparent': grandparent_tf,
                    'grandparent_direction': gp_direction,
                    'current_direction': current_direction
                }
    
    return 'ALIGNED', {
        'reason': 'Aligned with HTF',
        'parent': parent_tf,
        'parent_direction': parent_direction
    }


def main():
    print("=" * 60)
    print("HARDENED PREDICTION ENGINE v2.0")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Initialize components
    regime_detector = RegimeDetector(CONFIG)
    rules_engine = TradeRulesEngine(CONFIG)
    risk_manager = RiskManager(CONFIG)
    forward_tester = ForwardTester(
        os.path.join(os.path.dirname(__file__), CONFIG['paths']['forward_test_log'])
    )
    
    # Initialize news integration if enabled
    news_enabled = CONFIG.get('news', {}).get('enabled', False)
    if news_enabled:
        news_integration = get_news_integration(CONFIG)
        print("\n📰 News integration enabled")
        # Refresh news data at start
        news_integration.refresh_news(force=True)
    else:
        news_integration = None
    
    results = {}
    news_summary = None
    feature_cols = get_feature_columns()
    
    # Process in hierarchical order (1D first, then 4H, etc.)
    for tf in TIMEFRAME_HIERARCHY:
        print(f"\n{'='*40}")
        print(f"Processing {tf}...")
        print(f"{'='*40}")
        
        # 1. Load Artifacts
        model, calibrator = load_artifacts(tf)
        if not model:
            print(f"  ⚠️ Skipping {tf} - no model")
            continue
            
        # 2. Get Data & Features
        df = get_data(tf)
        if len(df) < 50:
            print(f"  ⚠️ Insufficient data for {tf} ({len(df)} rows)")
            continue
            
        df_proc = compute_indicators(df)
        
        if df_proc.empty:
            print(f"  ⚠️ No data after indicator computation for {tf}")
            continue
            
        latest_features = df_proc.iloc[[-1]]
        current_price = float(df_proc.iloc[-1]['Close'])
        timestamp = df_proc.index[-1].strftime('%Y-%m-%d %H:%M')
        
        # 3. Detect Regime (TF-aware)
        regime_state, regime_details = regime_detector.detect(df_proc, timeframe=tf)
        print(f"  📊 Regime: {regime_state}")
        
        # 4. Make Prediction
        X_live = latest_features[[c for c in feature_cols if c in latest_features.columns]]
        raw_prob_up = float(model.predict_proba(X_live)[0][1])
        
        raw_pred = 1 if raw_prob_up > 0.5 else 0
        direction = "UP" if raw_pred == 1 else "DOWN"
        
        # 5. Calibrate with drift warning
        calib_prob_up, has_drift_warning = calibrator.calibrate(raw_prob_up)
        
        # Calculate confidence for the predicted direction
        if direction == "UP":
            raw_conf = raw_prob_up
            final_conf = calib_prob_up
        else:
            raw_conf = 1.0 - raw_prob_up
            final_conf = 1.0 - calib_prob_up
        
        final_conf_pct = round(final_conf * 100, 2)
        raw_conf_pct = round(raw_conf * 100, 2)
        
        # Calibration drift check
        calibration_drift = abs(final_conf - raw_conf)
        if calibration_drift > 0.15:
            print(f"  ⚠️ Large calibration drift: {raw_conf_pct}% → {final_conf_pct}%")
        
        print(f"  🔮 Prediction: {direction}")
        print(f"     Raw Confidence: {raw_conf_pct}%")
        print(f"     Calibrated:     {final_conf_pct}%")
        
        # 6. Check HTF Alignment (CASCADING VALIDATION)
        htf_status, htf_details = check_htf_alignment(tf, direction, results)
        print(f"  🔗 HTF Status: {htf_status}")
        
        # 7. Rules Engine Check
        pred_packet = {'direction': direction, 'confidence': final_conf_pct}
        feat_dict = latest_features.iloc[0].to_dict()
        
        rules_decision, rules_reason = rules_engine.check_trade(
            tf, pred_packet, regime_state, feat_dict
        )
        
        # 8. Determine final decision incorporating HTF alignment
        decision = rules_decision
        rejection_reason = rules_reason
        
        if htf_status == 'HARD_CONFLICT' and decision == 'TRADE':
            decision = 'NO_TRADE'
            rejection_reason = 'HTF_CONFLICT'
        
        # 8.5 NEWS INTEGRATION: Apply news-based rules if enabled
        news_sentiment = 0.0
        news_label = 'NEUTRAL'
        news_risk_mult = 1.0
        news_headlines = []
        news_high_impact = False
        
        if news_integration:
            news_assessment = news_integration.get_news_assessment(tf)
            news_summary = news_assessment  # Store for output
            
            news_sentiment = news_assessment.get('sentiment_score', 0)
            news_label = news_assessment.get('sentiment_label', 'NEUTRAL')
            news_risk_mult = news_assessment.get('risk_multiplier', 1.0)
            news_headlines = news_assessment.get('headlines', [])[:5]
            news_high_impact = len(news_assessment.get('high_impact_events', [])) > 0
            
            # Check if news blocks the trade
            if decision == 'TRADE' and not news_assessment.get('can_trade', True):
                decision = 'NO_TRADE'
                rejection_reason = news_assessment.get('reason', 'HIGH_IMPACT_NEWS')
                print(f"  🔴 NEWS BLOCK: {rejection_reason}")
            
            # Optionally adjust confidence based on sentiment
            elif decision == 'TRADE':
                final_conf = news_integration.adjust_confidence(
                    final_conf, direction, news_sentiment
                )
                final_conf_pct = round(final_conf * 100, 2)
        
        # 9. Risk Management (even for NO_TRADE for display purposes)
        # Determine risk multiplier based on HTF alignment and news
        htf_risk_multiplier = 1.0
        if htf_status == 'SOFT_CONFLICT':
            htf_risk_multiplier = 0.5  # Reduce risk by 50%
        elif htf_status == 'HARD_CONFLICT':
            htf_risk_multiplier = 0.0  # Zero risk
        
        # Combine with news risk multiplier
        combined_risk_multiplier = htf_risk_multiplier * news_risk_mult
        
        setup = risk_manager.calculate_trade_params(
            df_proc,
            direction,
            final_conf,
            htf_risk_multiplier=combined_risk_multiplier,
            regime=regime_state
        )
        
        # If Risk Manager rejects, override decision
        if setup.get("decision") == "NO_TRADE":
            if decision == "TRADE":
                decision = "NO_TRADE"
                rejection_reason = setup.get("reason", "RISK_CHECK_FAILED")
        
        print(f"  🛡️ Decision: {decision}")
        if decision == "NO_TRADE":
            print(f"     Reason: {rejection_reason}")
        else:
            print(f"     Lots: {setup.get('lots')} | Risk: ${setup.get('risk_amount')} | RR: 1:{setup.get('rr_ratio')}")
        
        # 10. Log to Forward Tester
        log_packet = {
            'symbol': 'XAUUSD',
            'direction': direction,
            'raw_confidence': raw_conf,
            'calibrated_confidence': final_conf,
            'calibration_drift': calibration_drift,
            'regime': regime_state,
            'htf_status': htf_status,
            'htf_parent': htf_details.get('parent'),
            'decision': decision,
            'reason': rejection_reason,
            'entry': setup.get('entry', 0),
            'sl': setup.get('sl', 0),
            'tp': setup.get('tp', 0),
            'lots': setup.get('lots', 0),
            'risk_pct': setup.get('risk_pct', 0),
            'risk_amount': setup.get('risk_amount', 0),
            'rr_ratio': setup.get('rr_ratio', 0),
            'current_price': current_price,
            # News fields
            'news_sentiment': news_sentiment,
            'news_high_impact': news_high_impact,
            'news_headlines': '; '.join([h.get('headline', '')[:50] for h in news_headlines[:3]])
        }
        forward_tester.log_signal(tf, log_packet)
        
        # 11. Build Result Packet
        results[tf] = {
            "direction": direction,
            "confidence": final_conf_pct,
            "raw_confidence": raw_conf_pct,
            "calibration_drift": round(calibration_drift * 100, 2),
            "decision": decision,
            "rejection_reason": rejection_reason,
            "regime": regime_state,
            "regime_details": regime_details,
            "htf_status": htf_status,
            "htf_details": htf_details,
            "current_price": round(current_price, 2),
            "timestamp": timestamp,
            "setup": setup,
            # News data
            "news": {
                "sentiment_score": round(news_sentiment, 3),
                "sentiment_label": news_label,
                "risk_multiplier": news_risk_mult,
                "high_impact": news_high_impact,
                "headlines": news_headlines
            }
        }

    # Save Output
    out_path = os.path.join(os.path.dirname(__file__), CONFIG['paths']['predictions_file'])
    
    # Build news summary for output if enabled
    news_output = None
    if news_integration and news_summary:
        news_output = {
            'sentiment_score': news_summary.get('sentiment_score', 0),
            'sentiment_label': news_summary.get('sentiment_label', 'NEUTRAL'),
            'bullish_count': news_summary.get('bullish_count', 0),
            'bearish_count': news_summary.get('bearish_count', 0),
            'neutral_count': news_summary.get('neutral_count', 0),
            'high_impact_events': news_summary.get('high_impact_events', []),
            'upcoming_events': news_summary.get('upcoming_events', []),
            'headlines': news_summary.get('headlines', [])[:10],
            'can_trade': news_summary.get('can_trade', True),
            'block_reason': news_summary.get('reason')
        }
        # Save news state separately
        news_integration.save_news_state(os.path.dirname(__file__))
    
    final_output = {
        "generated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC'),
        "system_version": CONFIG['system']['version'],
        "predictions": results,
        "news": news_output
    }
    
    try:
        with open(out_path, 'w') as f:
            json.dump(final_output, f, indent=2)
        print(f"\n✅ Saved predictions to {out_path}")
    except Exception as e:
        print(f"\n❌ Error saving JSON: {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("PREDICTION SUMMARY")
    print("=" * 60)
    
    for tf in TIMEFRAME_HIERARCHY:
        if tf in results:
            r = results[tf]
            status_icon = "✅" if r['decision'] == 'TRADE' else "⛔"
            print(f"{tf:5s} | {r['direction']:4s} | Conf: {r['confidence']:5.1f}% | "
                  f"Regime: {r['regime']:20s} | {status_icon} {r['decision']}")
    
    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def main_live():
    """
    Run prediction in live mode using incremental data.
    Uses LivePredictor for efficient rolling predictions.
    """
    from live_predictor import run_live_prediction
    return run_live_prediction()


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Gold Price Prediction Engine',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python predict.py              # Batch mode (default)
  python predict.py --live       # Live mode with incremental updates
  python predict.py --once       # Single prediction, then exit
        """
    )
    
    parser.add_argument('--live', action='store_true',
                        help='Use live mode with incremental data updates')
    parser.add_argument('--once', action='store_true',
                        help='Run single prediction (same as default)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output')
    
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    
    if args.live:
        # Live mode - use LivePredictor with incremental data
        print("🔴 LIVE MODE - Using incremental data updates")
        main_live()
    else:
        # Batch mode - full data fetch (default)
        print("📦 BATCH MODE - Full data fetch")
        main()
