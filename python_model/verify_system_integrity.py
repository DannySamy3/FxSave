"""
System Integrity Verification Script
Verifies all system components are functioning correctly.
"""

import os
import json
import csv
from pathlib import Path
from datetime import datetime

def verify_system_integrity():
    """Comprehensive system integrity check"""
    base_dir = Path(__file__).parent
    
    print("=" * 70)
    print("GOLD-TRADE PRO v2.2.0 - SYSTEM INTEGRITY CHECK")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    issues = []
    warnings = []
    
    # 1. Check forward test log
    print("1. Forward Test Log")
    print("-" * 70)
    log_path = base_dir / "forward_test_log.csv"
    if log_path.exists():
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader)
                
            expected_cols = 23
            if len(header) == expected_cols:
                print(f"   [OK] Schema: {len(header)} columns (correct)")
            else:
                issues.append(f"Log schema mismatch: {len(header)} columns, expected {expected_cols}")
                print(f"   ✗ Schema: {len(header)} columns (expected {expected_cols})")
            
            # Check encoding
            print(f"   [OK] Encoding: UTF-8")
            
        except Exception as e:
            issues.append(f"Log file error: {e}")
            print(f"   ✗ Error reading log: {e}")
    else:
        warnings.append("Log file not found (will be created on first prediction)")
        print("   [WARN] Log file not found (will be created on first prediction)")
    
    # 2. Check models
    print("\n2. ML Models")
    print("-" * 70)
    timeframes = ['15m', '30m', '1h', '4h', '1d']
    models_ok = 0
    for tf in timeframes:
        model_path = base_dir / f"xgb_{tf}.pkl"
        if model_path.exists():
            size = model_path.stat().st_size / (1024 * 1024)  # MB
            print(f"   [OK] {tf:4s} model: {size:.2f} MB")
            models_ok += 1
        else:
            issues.append(f"Model missing: {tf}")
            print(f"   ✗ {tf:4s} model: NOT FOUND")
    
    if models_ok == 5:
        print(f"   [OK] All {models_ok}/5 models present")
    else:
        print(f"   [WARN] Only {models_ok}/5 models present")
    
    # 3. Check calibrators
    print("\n3. Calibrators")
    print("-" * 70)
    calibrators_ok = 0
    for tf in timeframes:
        cal_path = base_dir / f"calibrator_{tf}.pkl"
        if cal_path.exists():
            print(f"   ✓ {tf:4s} calibrator: Present")
            calibrators_ok += 1
        else:
            warnings.append(f"Calibrator missing: {tf} (will use uncalibrated)")
            print(f"   ⚠ {tf:4s} calibrator: NOT FOUND (uncalibrated)")
    
    if calibrators_ok == 5:
        print(f"   ✓ All {calibrators_ok}/5 calibrators present")
    else:
        print(f"   ⚠ Only {calibrators_ok}/5 calibrators present")
    
    # 4. Check cache data
    print("\n4. Cache Data")
    print("-" * 70)
    cache_dir = base_dir / "cache"
    if cache_dir.exists():
        cache_files = list(cache_dir.glob("GC_F_*.csv"))
        if cache_files:
            for tf in timeframes:
                cache_file = cache_dir / f"GC_F_{tf}.csv"
                if cache_file.exists():
                    # Count lines (rough estimate)
                    try:
                        with open(cache_file, 'r') as f:
                            lines = sum(1 for _ in f) - 1  # Exclude header
                        print(f"   ✓ {tf:4s} cache: {lines:,} rows")
                    except:
                        print(f"   ⚠ {tf:4s} cache: Present (cannot read)")
                else:
                    warnings.append(f"Cache missing: {tf}")
                    print(f"   ⚠ {tf:4s} cache: NOT FOUND")
        else:
            warnings.append("No cache files found")
            print("   ⚠ No cache files found")
    else:
        warnings.append("Cache directory not found")
        print("   ⚠ Cache directory not found")
    
    # 5. Check news state
    print("\n5. News Integration")
    print("-" * 70)
    news_state_path = base_dir / "news_state.json"
    if news_state_path.exists():
        try:
            with open(news_state_path, 'r') as f:
                news_state = json.load(f)
            timestamp = news_state.get('timestamp', 'Unknown')
            print(f"   ✓ News state file: Present")
            print(f"   ✓ Last update: {timestamp}")
        except:
            print(f"   ⚠ News state file: Present but unreadable")
    else:
        warnings.append("News state file not found (will be created on first prediction)")
        print("   ⚠ News state file: NOT FOUND (will be created on first prediction)")
    
    # Check API keys
    config_path = base_dir / "config.json"
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = json.load(f)
        news_config = config.get('news', {})
        api_keys = news_config.get('api_keys', {})
        configured = sum(1 for k, v in api_keys.items() if v)
        if configured == 3:
            print(f"   ✓ API keys: All {configured}/3 configured")
        elif configured > 0:
            warnings.append(f"Only {configured}/3 API keys configured")
            print(f"   ⚠ API keys: {configured}/3 configured (fallback will be used)")
        else:
            warnings.append("No API keys configured (fallback will be used)")
            print(f"   ⚠ API keys: 0/3 configured (fallback will be used)")
    
    # 6. Test regime detection
    print("\n6. Regime Detection Test")
    print("-" * 70)
    try:
        from data_manager import DataManager
        from features import compute_indicators
        from regime import RegimeDetector
        
        dm = DataManager()
        rd = RegimeDetector()
        
        test_tf = '1h'
        df = dm.get_data_for_prediction(test_tf, lookback=300)
        if df is not None and len(df) >= 300:
            df_proc = compute_indicators(df)
            if len(df_proc) >= 50:
                regime, details = rd.detect(df_proc, test_tf)
                if regime != 'UNKNOWN':
                    print(f"   ✓ Regime detection: {regime} (ADX: {details.get('adx', 'N/A')})")
                else:
                    issues.append("Regime detection returns UNKNOWN")
                    print(f"   ✗ Regime detection: UNKNOWN")
            else:
                issues.append(f"Feature computation returns insufficient data: {len(df_proc)} rows")
                print(f"   ✗ Feature computation: Only {len(df_proc)} rows (expected 50+)")
        else:
            issues.append(f"Data retrieval failed: {len(df) if df is not None else 0} rows")
            print(f"   ✗ Data retrieval: Failed")
    except Exception as e:
        issues.append(f"Regime detection test failed: {e}")
        print(f"   ✗ Regime detection test: ERROR - {e}")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    if not issues and not warnings:
        print("✓ All checks passed - System is ready for production")
    else:
        if issues:
            print(f"✗ {len(issues)} critical issue(s) found:")
            for issue in issues:
                print(f"  - {issue}")
        
        if warnings:
            print(f"\n⚠ {len(warnings)} warning(s):")
            for warning in warnings:
                print(f"  - {warning}")
    
    print("=" * 70)
    
    return len(issues) == 0

if __name__ == "__main__":
    verify_system_integrity()








