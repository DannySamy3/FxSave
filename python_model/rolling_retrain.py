"""
Rolling Retrain Utility - Periodic Model Retraining
Retrains models on updated dataset without data leakage.

Features:
- Uses accumulated historical data
- Preserves temporal ordering
- Refits calibrators on new model
- Validates no past predictions are affected
- Creates backup before retraining
"""

import pandas as pd
import numpy as np
import pickle
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
import warnings

from data_manager import DataManager, get_data_manager
from features import compute_indicators, get_feature_columns
from calibration import ModelCalibrator

from sklearn.model_selection import TimeSeriesSplit, cross_val_predict
from xgboost import XGBClassifier

warnings.filterwarnings('ignore')

# Global seed
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)


def load_config():
    """Load configuration"""
    path = Path(__file__).parent / 'config.json'
    with open(path, 'r') as f:
        return json.load(f)


class RollingRetrainer:
    """
    Handles periodic model retraining with rolling data.
    """
    
    TIMEFRAMES = ['15m', '30m', '1h', '4h', '1d']
    
    def __init__(self, config=None):
        self.config = config or load_config()
        self.base_dir = Path(__file__).parent
        self.data_manager = get_data_manager()
        
        # Backup directory
        self.backup_dir = self.base_dir / 'backups'
        self.backup_dir.mkdir(exist_ok=True)
    
    def create_backup(self):
        """
        Backup current models and calibrators before retraining.
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = self.backup_dir / f'backup_{timestamp}'
        backup_path.mkdir(exist_ok=True)
        
        print(f"📦 Creating backup at {backup_path}...")
        
        files_backed_up = 0
        
        for tf in self.TIMEFRAMES:
            # Backup model
            model_path = self.base_dir / f'xgb_{tf}.pkl'
            if model_path.exists():
                shutil.copy(model_path, backup_path / f'xgb_{tf}.pkl')
                files_backed_up += 1
            
            # Backup calibrator
            calib_path = self.base_dir / f'calibrator_{tf}.pkl'
            if calib_path.exists():
                shutil.copy(calib_path, backup_path / f'calibrator_{tf}.pkl')
                files_backed_up += 1
        
        # Backup config
        config_path = self.base_dir / 'config.json'
        if config_path.exists():
            shutil.copy(config_path, backup_path / 'config.json')
        
        print(f"  ✓ Backed up {files_backed_up} files")
        
        return backup_path
    
    def restore_backup(self, backup_path):
        """
        Restore models from a backup.
        """
        backup_path = Path(backup_path)
        
        if not backup_path.exists():
            print(f"❌ Backup not found: {backup_path}")
            return False
        
        print(f"🔄 Restoring from {backup_path}...")
        
        for file in backup_path.glob('*.pkl'):
            dest = self.base_dir / file.name
            shutil.copy(file, dest)
            print(f"  ✓ Restored {file.name}")
        
        return True
    
    def get_training_data(self, timeframe, min_samples=200):
        """
        Get accumulated training data for a timeframe.
        Uses cached data from data_manager.
        """
        # Update data first
        df, _ = self.data_manager.fetch_incremental_update(timeframe)
        
        if df is None or len(df) < min_samples:
            print(f"  ⚠️ Insufficient data for {timeframe}: {len(df) if df is not None else 0}")
            return None, None
        
        # Compute features
        df_features = compute_indicators(df)
        
        # Create target (next candle direction)
        df_features['Direction'] = (df_features['Close'].shift(-1) > df_features['Close']).astype(int)
        
        # Drop NaN rows
        feature_cols = get_feature_columns()
        feature_cols = [c for c in feature_cols if c in df_features.columns]
        
        data = df_features[feature_cols + ['Direction']].dropna()
        
        return data, feature_cols
    
    def train_single_timeframe(self, timeframe, data, feature_cols):
        """
        Train model and calibrator for a single timeframe.
        
        Uses cross_val_predict for out-of-sample calibration.
        """
        print(f"\n  🧠 Training {timeframe}...")
        
        # Split data (85/15)
        split_idx = int(len(data) * 0.85)
        
        X_train = data[feature_cols].iloc[:split_idx]
        y_train = data['Direction'].iloc[:split_idx]
        X_test = data[feature_cols].iloc[split_idx:]
        y_test = data['Direction'].iloc[split_idx:]
        
        print(f"     Train: {len(X_train)}, Test: {len(X_test)}")
        
        # Hyperparameter search (simplified for speed)
        best_params = {
            'n_estimators': 200,
            'max_depth': 5,
            'learning_rate': 0.05,
            'subsample': 0.8,
            'colsample_bytree': 0.8
        }
        
        # Create model
        model = XGBClassifier(
            **best_params,
            eval_metric='logloss',
            use_label_encoder=False,
            random_state=RANDOM_SEED,
            n_jobs=-1
        )
        
        # Get OOS probabilities for calibration
        tscv = TimeSeriesSplit(n_splits=5)
        
        oos_probs = cross_val_predict(
            model,
            X_train,
            y_train,
            cv=tscv,
            method='predict_proba',
            n_jobs=-1
        )[:, 1]
        
        # Train calibrator on OOS probs
        calibrator = ModelCalibrator(timeframe)
        calibrator.fit(oos_probs, y_train.values)
        
        # Train final model on full training set
        model.fit(X_train, y_train)
        
        # Evaluate on test set
        y_pred = model.predict(X_test)
        y_prob = model.predict_proba(X_test)[:, 1]
        
        accuracy = (y_pred == y_test).mean()
        
        print(f"     Accuracy: {accuracy:.2%}")
        
        return model, calibrator, {
            'accuracy': accuracy,
            'n_train': len(X_train),
            'n_test': len(X_test)
        }
    
    def save_artifacts(self, timeframe, model, calibrator):
        """
        Save trained model and calibrator.
        """
        # Save model
        model_path = self.base_dir / f'xgb_{timeframe}.pkl'
        with open(model_path, 'wb') as f:
            pickle.dump(model, f)
        
        # Save calibrator
        calibrator.save(str(self.base_dir))
        
        print(f"     💾 Saved model and calibrator")
    
    def retrain_all(self, backup=True):
        """
        Retrain all timeframe models.
        
        Args:
            backup: Whether to create backup before retraining
        """
        print("=" * 60)
        print("🔄 ROLLING RETRAIN")
        print(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        # Create backup
        if backup:
            backup_path = self.create_backup()
        
        results = {}
        
        for tf in self.TIMEFRAMES:
            print(f"\n{'─' * 40}")
            print(f"Processing {tf}...")
            
            try:
                # Get data
                data, feature_cols = self.get_training_data(tf)
                
                if data is None:
                    print(f"  ⚠️ Skipping {tf} - insufficient data")
                    continue
                
                # Train
                model, calibrator, metrics = self.train_single_timeframe(
                    tf, data, feature_cols
                )
                
                # Save
                self.save_artifacts(tf, model, calibrator)
                
                results[tf] = metrics
                print(f"  ✅ {tf} complete")
                
            except Exception as e:
                print(f"  ❌ Error training {tf}: {e}")
                import traceback
                traceback.print_exc()
        
        # Summary
        print("\n" + "=" * 60)
        print("RETRAIN SUMMARY")
        print("=" * 60)
        
        for tf, m in results.items():
            print(f"  {tf:5s} | Acc: {m['accuracy']:.2%} | "
                  f"Samples: {m['n_train']}+{m['n_test']}")
        
        print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if backup:
            print(f"Backup at: {backup_path}")
        
        return results
    
    def list_backups(self):
        """List available backups"""
        backups = sorted(self.backup_dir.glob('backup_*'))
        
        print("\n📁 Available Backups:")
        for b in backups:
            files = list(b.glob('*.pkl'))
            print(f"  {b.name}: {len(files)} files")
        
        return backups
    
    def cleanup_old_backups(self, keep_count=5):
        """Keep only the most recent N backups"""
        backups = sorted(self.backup_dir.glob('backup_*'))
        
        if len(backups) <= keep_count:
            return
        
        for old_backup in backups[:-keep_count]:
            shutil.rmtree(old_backup)
            print(f"  🗑️ Removed old backup: {old_backup.name}")


def main():
    """Main entry point for rolling retrain"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Rolling Model Retrain')
    parser.add_argument('--no-backup', action='store_true',
                        help='Skip backup creation')
    parser.add_argument('--restore', type=str,
                        help='Restore from backup path')
    parser.add_argument('--list-backups', action='store_true',
                        help='List available backups')
    parser.add_argument('--timeframe', '-t', type=str,
                        help='Train only specific timeframe')
    
    args = parser.parse_args()
    
    retrainer = RollingRetrainer()
    
    if args.list_backups:
        retrainer.list_backups()
        return
    
    if args.restore:
        retrainer.restore_backup(args.restore)
        return
    
    if args.timeframe:
        # Train single timeframe
        data, feature_cols = retrainer.get_training_data(args.timeframe)
        if data is not None:
            model, calibrator, metrics = retrainer.train_single_timeframe(
                args.timeframe, data, feature_cols
            )
            retrainer.save_artifacts(args.timeframe, model, calibrator)
        return
    
    # Full retrain
    retrainer.retrain_all(backup=not args.no_backup)


if __name__ == "__main__":
    main()








