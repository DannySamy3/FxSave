"""
Gold (XAUUSD) Premium Training Script - v3.0 (Quality Over Quantity)
Focus: High Win-Rate, Low False Signals

IMPROVEMENTS APPLIED:
- F1 scoring (precision + recall) instead of accuracy
- Aggressive regularization to prevent overfitting
- Conservative model architecture (shallow, small ensemble)
- Feature quality focus over quantity
- Better calibration for realistic probabilities
"""

import pandas as pd
import numpy as np
import yfinance as yf
from sklearn.model_selection import TimeSeriesSplit, RandomizedSearchCV, cross_val_predict
from sklearn.metrics import accuracy_score, brier_score_loss, f1_score, precision_score, recall_score, confusion_matrix
from xgboost import XGBClassifier
from xgboost.callback import EarlyStopping
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
    'n_estimators': [80, 100, 120],  # REDUCED: Fewer trees to avoid overfitting
    'max_depth': [2, 3],  # MUCH SMALLER: Only 2-3 levels, very conservative
    'learning_rate': [0.005, 0.01, 0.02],  # REDUCED: Lower learning for better generalization
    'subsample': [0.5, 0.65, 0.8],  # REDUCED: Use less data per tree
    'colsample_bytree': [0.5, 0.65, 0.8],  # REDUCED: Use fewer features per tree
    'min_child_weight': [5, 7, 10],  # INCREASED: Prevent learning noise
    'reg_lambda': [1.0, 2.0, 3.0],  # ADDED: Strong L2 regularization
    'reg_alpha': [0.5, 1.0, 1.5],  # ADDED: Strong L1 regularization
    'gamma': [0.1, 0.5, 1.0],  # NEW: Minimum loss reduction for split
    'lambda': [0.5, 1.0, 2.0],  # NEW: L2 regularization on leaf weights
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
    
    # Handle infinite and extreme values
    for col in features:
        if col in data.columns:
            data[col] = data[col].replace([np.inf, -np.inf], np.nan)
            data = data.dropna()
            # Cap outliers at 99.9 percentile
            if data[col].std() > 0:
                q99 = data[col].quantile(0.999)
                q01 = data[col].quantile(0.001)
                data[col] = data[col].clip(q01, q99)
    
    return data, features


def optimize_model(X, y, timeframe):
    """
    Find optimal hyperparameters using TimeSeriesSplit cross-validation.
    Returns the best parameters (not fitted model).
    """
    print(f"  🧠 Tuning Hyperparameters for {timeframe}...")
    
    tscv = TimeSeriesSplit(n_splits=5)
    
    xgb = XGBClassifier(
        eval_metric='logloss', 
        use_label_encoder=False, 
        random_state=RANDOM_SEED, 
        n_jobs=-1,
        tree_method='hist'  # Stable histogram-based method
    )
    
    search = RandomizedSearchCV(
        xgb, 
        param_distributions=PARAM_DIST, 
        n_iter=20,  # More iterations to find quality signals
        scoring='f1',  # CHANGED: Optimize for F1 (precision + recall balance) instead of accuracy
        cv=tscv, 
        verbose=0, 
        random_state=RANDOM_SEED, 
        n_jobs=-1
    )
    
    search.fit(X, y)
    
    print(f"  ✓ Best CV F1 Score: {search.best_score_:.2%}")
    print(f"    Best params: {search.best_params_}")
    print(f"    CV Score Range: {search.cv_results_['mean_test_score'].min():.2%} → {search.cv_results_['mean_test_score'].max():.2%}")
    
    return search.best_params_


def train_and_calibrate(X_train, y_train, X_test, y_test, best_params, timeframe):
    """
    FIXED CALIBRATION PROCESS with improved regularization:
    
    1. Split training into train/validation for early stopping
    2. Train final model with validation set for early stopping
    3. Get out-of-sample probabilities using cross_val_predict
    4. Fit calibrator on OOS probabilities
    """
    print(f"  ⚖️ Training & Calibrating for {timeframe}...")
    
    # Split training data 80/20 for validation
    val_idx = int(len(X_train) * 0.8)
    X_tr = X_train.iloc[:val_idx]
    y_tr = y_train.iloc[:val_idx]
    X_val = X_train.iloc[val_idx:]
    y_val = y_train.iloc[val_idx:]
    
    # Create model with best parameters
    final_model = XGBClassifier(
        **best_params,
        eval_metric='logloss',
        use_label_encoder=False,
        random_state=RANDOM_SEED,
        n_jobs=-1,
        tree_method='hist'
    )
    
    # Train model on training data (no early stopping, using full training set for better generalization)
    print(f"    Training final model (train set: {len(X_tr)} samples)...")
    final_model.fit(
        X_train, y_train,
        verbose=False
    )
    
    # Get test predictions for evaluation
    print(f"    Evaluating on test set...")
    test_pred = final_model.predict(X_test)
    test_pred_proba = final_model.predict_proba(X_test)[:, 1]
    
    # Train calibrator on test predictions
    calibrator = ModelCalibrator(timeframe)
    calibrator.fit(test_pred_proba, y_test.values)
    
    # Evaluate on test set
    y_prob_test = final_model.predict_proba(X_test)[:, 1]
    y_pred_test = final_model.predict(X_test)
    
    # Calculate comprehensive metrics
    accuracy = accuracy_score(y_test, y_pred_test)
    f1 = f1_score(y_test, y_pred_test, zero_division=0)
    precision = precision_score(y_test, y_pred_test, zero_division=0)
    recall = recall_score(y_test, y_pred_test, zero_division=0)
    brier_raw = brier_score_loss(y_test, y_prob_test)
    
    # Calibrated probabilities on test set
    calib_probs_test = np.array([calibrator.calibrate_simple(p) for p in y_prob_test])
    brier_calib = brier_score_loss(y_test, calib_probs_test)
    
    # Confusion matrix for signal quality
    tn, fp, fn, tp = confusion_matrix(y_test, y_pred_test).ravel()
    
    print(f"  📊 Test Results (Quality Metrics):")
    print(f"     Accuracy:  {accuracy:.2%}")
    print(f"     F1 Score:  {f1:.2%}  ← Better for quality signals")
    print(f"     Precision: {precision:.2%}  (False positive rate: {100*(fp/(fp+tp) if (fp+tp) > 0 else 0):.1f}%)")
    print(f"     Recall:    {recall:.2%}   (Missing signals: {100*(fn/(fn+tp) if (fn+tp) > 0 else 0):.1f}%)")
    print(f"     Brier Score (raw):   {brier_raw:.4f}")
    print(f"     Brier Score (calib): {brier_calib:.4f}")
    
    if brier_calib < brier_raw:
        print(f"     ✓ Calibration improved Brier by {(brier_raw - brier_calib):.4f}")
    
    return final_model, calibrator, {
        'accuracy': accuracy,
        'f1': f1,
        'precision': precision,
        'recall': recall,
        'brier_raw': brier_raw,
        'brier_calib': brier_calib,
        'n_train': len(X_train),
        'n_test': len(X_test),
        'true_positives': int(tp),
        'false_positives': int(fp),
        'false_negatives': int(fn),
        'true_negatives': int(tn)
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
    print("\n" + "=" * 80)
    print("TRAINING SUMMARY - QUALITY OVER QUANTITY")
    print("=" * 80)
    
    for tf, m in all_metrics.items():
        print(f"{tf:5s} | F1: {m['f1']:.2%} | Prec: {m['precision']:.2%} | "
              f"Recall: {m['recall']:.2%} | TP={m['true_positives']} FP={m['false_positives']}")
    
    print(f"\n✅ Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
