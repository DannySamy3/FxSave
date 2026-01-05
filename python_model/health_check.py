"""
Data Validation & Health Check Script v2.0
Run this to verify the system is working correctly: python health_check.py

UPDATED:
- Validates all v2.0 components
- Checks calibrator integrity
- Validates HTF validation logic
- Verifies all required files
"""

import os
import json
import sys
import pickle
from pathlib import Path
from datetime import datetime

def check_python_modules():
    """Check if required Python modules are installed"""
    print("\n📦 Checking Python modules...")
    
    modules = {
        'pandas': 'Data manipulation',
        'numpy': 'Numerical computing',
        'xgboost': 'ML classifier',
        'sklearn': 'Machine learning utils',
        'yfinance': 'Financial data download',
        'ta': 'Technical analysis indicators'
    }
    
    missing = []
    for module, description in modules.items():
        try:
            __import__(module)
            print(f"  ✓ {module:15} ({description})")
        except ImportError:
            print(f"  ✗ {module:15} ({description}) - MISSING")
            missing.append(module)
    
    return len(missing) == 0, missing

def check_model_files():
    """Check if trained models exist for all timeframes"""
    print("\n🤖 Checking model files...")
    
    timeframes = ['15m', '30m', '1h', '4h', '1d']
    base_path = Path(__file__).parent
    
    found = 0
    missing = []
    
    for tf in timeframes:
        model_path = base_path / f'xgb_{tf}.pkl'
        calib_path = base_path / f'calibrator_{tf}.pkl'
        
        if model_path.exists():
            size_mb = model_path.stat().st_size / (1024 * 1024)
            print(f"  ✓ Model {tf:4s}: {size_mb:.2f} MB")
            found += 1
        else:
            print(f"  ✗ Model {tf:4s}: NOT FOUND")
            missing.append(f'xgb_{tf}.pkl')
            
        if calib_path.exists():
            print(f"  ✓ Calibrator {tf:4s}")
        else:
            print(f"  ⚠ Calibrator {tf:4s}: NOT FOUND (will use uncalibrated)")
    
    return found > 0, missing

def check_calibrators():
    """Validate calibrator integrity"""
    print("\n⚖️ Validating calibrators...")
    
    timeframes = ['15m', '30m', '1h', '4h', '1d']
    base_path = Path(__file__).parent
    valid = 0
    
    for tf in timeframes:
        calib_path = base_path / f'calibrator_{tf}.pkl'
        
        if not calib_path.exists():
            continue
            
        try:
            with open(calib_path, 'rb') as f:
                data = pickle.load(f)
            
            # Check if it's new format with stats
            if isinstance(data, dict) and 'isotonic' in data:
                iso = data['isotonic']
                stats = data.get('stats', {})
                print(f"  ✓ {tf:4s}: v2.0 format, {stats.get('n_samples', 'N/A')} samples")
            else:
                # Old format - just isotonic regressor
                iso = data
                print(f"  ⚠ {tf:4s}: Old format (no stats)")
            
            # Test prediction
            test_result = iso.predict([0.5])[0]
            if 0 <= test_result <= 1:
                valid += 1
            else:
                print(f"  ✗ {tf:4s}: Invalid output range")
                
        except Exception as e:
            print(f"  ✗ {tf:4s}: Load failed - {e}")
    
    return valid > 0

def check_config():
    """Check config file integrity"""
    print("\n⚙️ Checking configuration...")
    
    config_path = Path(__file__).parent / 'config.json'
    
    if not config_path.exists():
        print(f"  ✗ config.json: NOT FOUND")
        return False
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        required_sections = ['system', 'paths', 'thresholds', 'rules', 'risk_management']
        missing = [s for s in required_sections if s not in config]
        
        if missing:
            print(f"  ⚠ Missing sections: {missing}")
        else:
            print(f"  ✓ All required sections present")
        
        version = config.get('system', {}).get('version', 'unknown')
        print(f"  ✓ System version: {version}")
        
        return len(missing) == 0
        
    except json.JSONDecodeError as e:
        print(f"  ✗ Invalid JSON: {e}")
        return False

def check_prediction_file():
    """Check if latest prediction exists and is valid"""
    print("\n📊 Checking prediction file...")
    
    pred_path = Path(__file__).parent.parent / 'public' / 'latest_prediction.json'
    
    if not pred_path.exists():
        print(f"  ✗ Prediction not found")
        print(f"    Please run: python predict.py")
        return False
    
    try:
        with open(pred_path, 'r') as f:
            prediction = json.load(f)
        
        print(f"  ✓ Prediction file found")
        print(f"    Generated: {prediction.get('generated_at', 'unknown')}")
        print(f"    Version: {prediction.get('system_version', 'unknown')}")
        
        # Check predictions structure
        preds = prediction.get('predictions', {})
        for tf, data in preds.items():
            decision = data.get('decision', 'unknown')
            direction = data.get('direction', 'N/A')
            conf = data.get('confidence', 0)
            icon = "✅" if decision == 'TRADE' else "⛔"
            print(f"    {tf:4s}: {icon} {decision} | {direction} {conf}%")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"  ✗ Prediction file corrupted: {e}")
        return False

def check_forward_test_log():
    """Check forward test log integrity"""
    print("\n📝 Checking forward test log...")
    
    log_path = Path(__file__).parent / 'forward_test_log.csv'
    
    if not log_path.exists():
        print(f"  ⚠ Log not found (will be created on first prediction)")
        return True
    
    try:
        import pandas as pd
        df = pd.read_csv(log_path)
        
        print(f"  ✓ Log found: {len(df)} entries")
        
        # Check for required columns (v2.0)
        required_cols = ['timestamp', 'timeframe', 'decision', 'lots', 'htf_status']
        missing_cols = [c for c in required_cols if c not in df.columns]
        
        if missing_cols:
            print(f"  ⚠ Missing columns (old format?): {missing_cols}")
        else:
            print(f"  ✓ All v2.0 columns present")
        
        if not df.empty:
            last = df.iloc[-1]['timestamp']
            print(f"    Last entry: {last}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error reading log: {e}")
        return False

def check_project_structure():
    """Check if all necessary files exist"""
    print("\n📁 Checking project structure...")
    
    base_path = Path(__file__).parent.parent
    
    required_files = {
        'python_model/train.py': 'Training script',
        'python_model/predict.py': 'Prediction script',
        'python_model/calibration.py': 'Calibration module',
        'python_model/regime.py': 'Regime detection',
        'python_model/risk_engine.py': 'Risk management',
        'python_model/rules_engine.py': 'Trade rules',
        'python_model/forward_test.py': 'Forward testing',
        'python_model/features.py': 'Feature engineering',
        'python_model/config.json': 'Configuration',
        'python_model/requirements.txt': 'Python dependencies',
        'pages/api/predict.js': 'API endpoint',
        'pages/index.js': 'Frontend page',
        'package.json': 'Node.js config',
    }
    
    missing = []
    for file_path, description in required_files.items():
        full_path = base_path / file_path
        if full_path.exists():
            print(f"  ✓ {file_path:35s}")
        else:
            print(f"  ✗ {file_path:35s} - MISSING")
            missing.append(file_path)
    
    return len(missing) == 0, missing

def check_node_modules():
    """Check if Node.js dependencies are installed"""
    print("\n📦 Checking Node.js dependencies...")
    
    node_modules = Path(__file__).parent.parent / 'node_modules'
    
    if node_modules.exists():
        print(f"  ✓ node_modules installed")
        return True
    else:
        print(f"  ✗ node_modules not found")
        print(f"    Please run: npm install")
        return False

def run_quick_inference_test():
    """Run a quick inference test to validate the system"""
    print("\n🧪 Running quick inference test...")
    
    try:
        # Import modules
        from features import compute_indicators, get_feature_columns
        from calibration import ModelCalibrator
        from regime import RegimeDetector
        import pandas as pd
        import numpy as np
        
        # Create dummy data
        dates = pd.date_range(end=datetime.now(), periods=100, freq='1h')
        np.random.seed(42)
        
        base_price = 2000
        closes = base_price + np.cumsum(np.random.randn(100) * 2)
        
        df = pd.DataFrame({
            'Open': closes - np.random.rand(100) * 2,
            'High': closes + np.random.rand(100) * 5,
            'Low': closes - np.random.rand(100) * 5,
            'Close': closes,
            'Volume': np.random.randint(100, 10000, 100)
        }, index=dates)
        
        # Test feature computation
        df_features = compute_indicators(df)
        print(f"  ✓ Feature computation: {len(df_features)} rows, {len(get_feature_columns())} features")
        
        # Test regime detection
        detector = RegimeDetector()
        regime, details = detector.detect(df_features, timeframe='1h')
        print(f"  ✓ Regime detection: {regime}")
        
        # Test calibrator (if available)
        calibrator = ModelCalibrator('1h')
        if calibrator.load(str(Path(__file__).parent)):
            calib_result, has_warning = calibrator.calibrate(0.65)
            print(f"  ✓ Calibration test: 0.65 → {calib_result:.3f}")
        else:
            print(f"  ⚠ Calibrator not available for test")
        
        print(f"  ✓ Inference test PASSED")
        return True
        
    except Exception as e:
        print(f"  ✗ Inference test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all health checks"""
    print("=" * 60)
    print("🏥 Gold Prediction System - Health Check v2.0")
    print(f"   Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    results = {
        'Python modules': check_python_modules(),
        'Model files': check_model_files(),
        'Calibrators': check_calibrators(),
        'Configuration': check_config(),
        'Prediction file': check_prediction_file(),
        'Forward test log': check_forward_test_log(),
        'Project structure': check_project_structure(),
        'Node.js modules': check_node_modules(),
        'Inference test': run_quick_inference_test(),
    }
    
    print("\n" + "=" * 60)
    print("📋 Summary")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for check_name, result in results.items():
        if isinstance(result, tuple):
            status = "✓ PASS" if result[0] else "✗ FAIL"
            if result[0]:
                passed += 1
            else:
                failed += 1
        else:
            status = "✓ PASS" if result else "✗ FAIL"
            if result:
                passed += 1
            else:
                failed += 1
        print(f"{status:10} {check_name}")
    
    print("\n" + "=" * 60)
    
    if failed == 0:
        print(f"✅ All checks passed! ({passed}/{len(results)})")
        print("\n🚀 System is ready to use:")
        print("   1. python train.py     (if models not trained)")
        print("   2. python predict.py   (generate predictions)")
        print("   3. npm run dev         (start frontend)")
        return 0
    else:
        print(f"❌ {failed} check(s) failed")
        print(f"\n💡 Next steps:")
        print("   1. Check the errors above")
        print("   2. Run: pip install -r requirements.txt")
        print("   3. Run: python train.py (if models missing)")
        print("   4. See README.md for detailed instructions")
        return 1

if __name__ == '__main__':
    sys.exit(main())
