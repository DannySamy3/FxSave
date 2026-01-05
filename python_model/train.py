"""
Gold (XAUUSD) Intensive Training Script - HARDENED v2.0
Includes: Hyperparameter Tuning, Cross-Validation, AND PROBABILITY CALIBRATION.

FIXES APPLIED:
- Calibrator now trained on SAME model used for production (no distribution mismatch)
- Uses cross_val_predict for out-of-sample calibration probabilities
- Added deterministic seeding throughout
- Improved validation and error handling
"""

import pandas as pd
import numpy as np
import yfinance as yf
from sklearn.model_selection import TimeSeriesSplit, RandomizedSearchCV, cross_val_predict
from sklearn.metrics import accuracy_score, brier_score_loss
from xgboost import XGBClassifier
import pickle
import os
import sys
import warnings
from datetime import datetime
from features import compute_indicators, get_feature_columns
from calibration import ModelCalibrator

warnings.filterwarnings('ignore')

# Global seed for reproducibility
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)

# 1. Configuration
TIMEFRAMES = {
    '15m': {'period': '59d', 'interval': '15m'},
    '30m': {'period': '59d', 'interval': '30m'},
    '1h':  {'period': '729d', 'interval': '1h'},
    '4h':  {'period': '729d', 'interval': '1h'},
    '1d':  {'period': 'max',  'interval': '1d'}
}

PARAM_DIST = {
    'n_estimators': [100, 200, 300],
    'max_depth': [3, 5, 7],
    'learning_rate': [0.01, 0.05, 0.1],
    'subsample': [0.7, 0.8, 0.9],
    'colsample_bytree': [0.7, 0.8, 0.9]
}


def download_data(timeframe):
    """Download data from Yahoo Finance with error handling"""
    cfg = TIMEFRAMES[timeframe]
    print(f"\n📥 Fetching {timeframe} data...")
    
    try:
        df = yf.download('GC=F', period=cfg['period'], interval=cfg['interval'], progress=False)
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        if timeframe == '4h':
            print("  ⟳ Resampling to 4h...")
            logic = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
            logic = {k: v for k, v in logic.items() if k in df.columns}
            df = df.resample('4h').agg(logic).dropna()
        
        print(f"  ✓ Downloaded {len(df)} rows")
        return df
        
    except Exception as e:
        print(f"  ❌ Error downloading {timeframe}: {e}")
        return pd.DataFrame()


def prepare_data(df):
    """Prepare features and target with correct shift for no leakage"""
    df = compute_indicators(df)
    
    # Target: 1 if NEXT candle closes higher than current
    # Using shift(-1) correctly to look at future price
    df['Direction'] = (df['Close'].shift(-1) > df['Close']).astype(int)
    
    features = get_feature_columns()
    features = [c for c in features if c in df.columns]
    
    # Drop the last row (no future data for target) and any NaN rows
    data = df[features + ['Direction']].dropna()
    
    return data, features


def optimize_model(X, y, timeframe):
    """
    Find optimal hyperparameters using TimeSeriesSplit cross-validation.
    Returns the best parameters (not fitted model).
    """
    print(f"  🧠 Tuning Hyperparameters for {timeframe}...")
    
    tscv = TimeSeriesSplit(n_splits=5)  # Increased from 3 to 5 for better estimation
    
    xgb = XGBClassifier(
        eval_metric='logloss', 
        use_label_encoder=False, 
        random_state=RANDOM_SEED, 
        n_jobs=-1
    )
    
    search = RandomizedSearchCV(
        xgb, 
        param_distributions=PARAM_DIST, 
        n_iter=10,  # Increased from 5
        scoring='accuracy', 
        cv=tscv, 
        verbose=0, 
        random_state=RANDOM_SEED, 
        n_jobs=-1
    )
    
    search.fit(X, y)
    
    print(f"  ✓ Best CV Accuracy: {search.best_score_:.2%}")
    print(f"    Best params: {search.best_params_}")
    
    return search.best_params_


def train_and_calibrate(X_train, y_train, X_test, y_test, best_params, timeframe):
    """
    FIXED CALIBRATION PROCESS:
    
    1. Train final model on full training data with best params
    2. Get out-of-sample probabilities using cross_val_predict on training data
    3. Fit calibrator on these OOS probabilities
    4. The production model IS the same model calibrator was trained on
    
    This ensures no distribution mismatch between calibrator and production model.
    """
    print(f"  ⚖️ Training & Calibrating for {timeframe}...")
    
    # Create model with best parameters
    final_model = XGBClassifier(
        **best_params,
        eval_metric='logloss',
        use_label_encoder=False,
        random_state=RANDOM_SEED,
        n_jobs=-1
    )
    
    # STEP 1: Get out-of-sample probability predictions via cross-validation
    # This gives us probabilities that are "unseen" by the model that made them
    tscv = TimeSeriesSplit(n_splits=5)
    
    print(f"    Getting OOS probabilities via cross_val_predict...")
    oos_probs = cross_val_predict(
        final_model, 
        X_train, 
        y_train, 
        cv=tscv, 
        method='predict_proba',
        n_jobs=-1
    )[:, 1]  # Get probability for class 1 (UP)
    
    # STEP 2: Train calibrator on these OOS probabilities
    calibrator = ModelCalibrator(timeframe)
    calibrator.fit(oos_probs, y_train.values)
    
    # STEP 3: Now train the FINAL model on ALL training data
    # This is the model that will be saved and used for production
    final_model.fit(X_train, y_train)
    
    # STEP 4: Evaluate on test set
    y_prob_test = final_model.predict_proba(X_test)[:, 1]
    y_pred_test = final_model.predict(X_test)
    
    # Calculate metrics
    accuracy = accuracy_score(y_test, y_pred_test)
    brier_raw = brier_score_loss(y_test, y_prob_test)
    
    # Calibrated probabilities on test set
    calib_probs_test = np.array([calibrator.calibrate_simple(p) for p in y_prob_test])
    brier_calib = brier_score_loss(y_test, calib_probs_test)
    
    print(f"  📊 Test Results:")
    print(f"     Accuracy: {accuracy:.2%}")
    print(f"     Brier Score (raw):   {brier_raw:.4f}")
    print(f"     Brier Score (calib): {brier_calib:.4f}")
    
    if brier_calib < brier_raw:
        print(f"     ✓ Calibration improved Brier by {(brier_raw - brier_calib):.4f}")
    else:
        print(f"     ⚠️ Calibration did not improve Brier score")
    
    return final_model, calibrator, {
        'accuracy': accuracy,
        'brier_raw': brier_raw,
        'brier_calib': brier_calib,
        'n_train': len(X_train),
        'n_test': len(X_test)
    }


def save_artifacts(model, calibrator, timeframe, metrics):
    """Save model, calibrator, and training metadata"""
    base_dir = os.path.dirname(__file__)
    
    # Save Model
    m_path = os.path.join(base_dir, f'xgb_{timeframe}.pkl')
    with open(m_path, 'wb') as f:
        pickle.dump(model, f)
    
    # Save Calibrator
    calibrator.save(base_dir)
    
    # Save training metadata
    metadata = {
        'timeframe': timeframe,
        'trained_at': datetime.now().isoformat(),
        'metrics': metrics,
        'random_seed': RANDOM_SEED,
        'version': '2.0'
    }
    
    meta_path = os.path.join(base_dir, f'meta_{timeframe}.pkl')
    with open(meta_path, 'wb') as f:
        pickle.dump(metadata, f)
    
    print(f"  💾 Saved Model, Calibrator & Metadata for {timeframe}")


def main():
    print("=" * 60)
    print("XAUUSD HARDENED TRAINING ENGINE v2.0")
    print(f"Random Seed: {RANDOM_SEED}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    all_metrics = {}
    
    for tf in TIMEFRAMES.keys():
        try:
            # 1. Download Data
            df = download_data(tf)
            if len(df) < 200:
                print(f"  ⚠️ Insufficient data for {tf} ({len(df)} rows)")
                continue
            
            # 2. Prepare Features & Target
            data, feature_cols = prepare_data(df)
            print(f"  ✓ Prepared {len(data)} samples with {len(feature_cols)} features")
            
            if len(data) < 100:
                print(f"  ⚠️ Too few samples after feature computation for {tf}")
                continue
            
            # 3. Train/Test Split (85/15 temporal split)
            split_idx = int(len(data) * 0.85)
            
            X_train = data[feature_cols].iloc[:split_idx]
            y_train = data['Direction'].iloc[:split_idx]
            X_test = data[feature_cols].iloc[split_idx:]
            y_test = data['Direction'].iloc[split_idx:]
            
            print(f"  📊 Split: Train={len(X_train)}, Test={len(X_test)}")
            
            # 4. Optimize Hyperparameters
            best_params = optimize_model(X_train, y_train, tf)
            
            # 5. Train & Calibrate (FIXED: Same model for both)
            model, calibrator, metrics = train_and_calibrate(
                X_train, y_train, X_test, y_test, best_params, tf
            )
            
            # 6. Save Artifacts
            save_artifacts(model, calibrator, tf, metrics)
            
            all_metrics[tf] = metrics
            
            print(f"  🏆 {tf} COMPLETE\n")
            
        except Exception as e:
            print(f"  ❌ Error training {tf}: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print("\n" + "=" * 60)
    print("TRAINING SUMMARY")
    print("=" * 60)
    
    for tf, m in all_metrics.items():
        print(f"{tf:5s} | Acc: {m['accuracy']:.2%} | "
              f"Brier: {m['brier_raw']:.4f} → {m['brier_calib']:.4f} | "
              f"Samples: {m['n_train']}+{m['n_test']}")
    
    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
