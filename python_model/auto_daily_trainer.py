"""
Daily Auto-Trainer - Continuous Learning System
Automatically retrains model each day with new market data
Only deploys if new model is BETTER than old one

Features:
- Runs daily (can be triggered manually)
- Fetches new data and retrains
- Validates new model performance
- Compares with old model
- Only deploys if improvement detected
- Keeps backup of all models
- Logs all training results
- Prevents overfitting with strict thresholds
"""

import pandas as pd
import numpy as np
import yfinance as yf
import pickle
import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import warnings
from sklearn.model_selection import TimeSeriesSplit, cross_val_predict
from sklearn.metrics import f1_score, precision_score, recall_score, accuracy_score, confusion_matrix
from xgboost import XGBClassifier

from features import compute_indicators, get_feature_columns
from calibration import ModelCalibrator

warnings.filterwarnings('ignore')

RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)


class AutoTrainer:
    """Continuous learning system for daily model updates"""
    
    TIMEFRAMES = {
        '15m': {'period': '59d', 'interval': '15m'},
        '30m': {'period': '59d', 'interval': '30m'},
        '1h':  {'period': '729d', 'interval': '1h'},
        '4h':  {'period': '729d', 'interval': '1h'},
        '1d':  {'period': 'max',  'interval': '1d'}
    }
    
    def __init__(self, config_path='config.json'):
        """Initialize auto-trainer"""
        self.base_dir = Path(__file__).parent
        self.config = self._load_config(config_path)
        self.backup_dir = self.base_dir / 'model_backups'
        self.log_file = self.base_dir / 'daily_training.log'
        self.backup_dir.mkdir(exist_ok=True)
        
        # Performance thresholds for deployment
        self.min_f1_improvement = 0.01  # At least 1% F1 improvement
        self.max_f1_regression = -0.02  # Don't allow 2%+ drop
        
    def _load_config(self, path):
        """Load configuration"""
        with open(self.base_dir / path, 'r') as f:
            return json.load(f)
    
    def _log(self, message):
        """Log message to file and print"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_msg = f"[{timestamp}] {message}"
        print(log_msg)
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_msg + '\n')
        except Exception as e:
            print(f"Log write error: {e}")
    
    def backup_current_models(self):
        """Create backup of current models"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_subdir = self.backup_dir / f"backup_{timestamp}"
        backup_subdir.mkdir(exist_ok=True)
        
        for tf in self.TIMEFRAMES.keys():
            model_file = self.base_dir / f'xgb_{tf}.pkl'
            calib_file = self.base_dir / f'calibrator_{tf}.pkl'
            meta_file = self.base_dir / f'metadata_{tf}.json'
            
            if model_file.exists():
                shutil.copy(model_file, backup_subdir / f'xgb_{tf}.pkl')
            if calib_file.exists():
                shutil.copy(calib_file, backup_subdir / f'calibrator_{tf}.pkl')
            if meta_file.exists():
                shutil.copy(meta_file, backup_subdir / f'metadata_{tf}.json')
        
        self._log(f"✅ Backed up models to {backup_subdir}")
        return backup_subdir
    
    def fetch_data(self, timeframe):
        """Fetch latest data from Yahoo Finance"""
        try:
            period = self.TIMEFRAMES[timeframe]['period']
            interval = self.TIMEFRAMES[timeframe]['interval']
            
            df = yf.download('GC=F', period=period, interval=interval, progress=False)
            
            if df is None or len(df) < 50:
                return None
            
            # Handle MultiIndex columns from yfinance
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            return df.sort_index()
        except Exception as e:
            self._log(f"❌ Error fetching {timeframe} data: {e}")
            return None
    
    def prepare_data(self, df):
        """Prepare features and target"""
        try:
            df = compute_indicators(df)
            df['Direction'] = (df['Close'].shift(-1) > df['Close']).astype(int)
            
            features = get_feature_columns()
            features = [c for c in features if c in df.columns]
            
            data = df[features + ['Direction']].dropna()
            
            # Clean outliers
            for col in features:
                if col in data.columns:
                    data[col] = data[col].replace([np.inf, -np.inf], np.nan)
                    data = data.dropna()
                    if data[col].std() > 0:
                        q99 = data[col].quantile(0.999)
                        q01 = data[col].quantile(0.001)
                        data[col] = data[col].clip(q01, q99)
            
            return data, features
        except Exception as e:
            self._log(f"❌ Error preparing data: {e}")
            return None, None
    
    def train_model(self, X_train, y_train, best_params):
        """Train new model with best parameters"""
        model = XGBClassifier(
            **best_params,
            eval_metric='logloss',
            use_label_encoder=False,
            random_state=RANDOM_SEED,
            n_jobs=-1,
            tree_method='hist'
        )
        
        model.fit(X_train, y_train, verbose=False)
        return model
    
    def evaluate_model(self, model, X_test, y_test):
        """Evaluate model and return comprehensive metrics"""
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]
        
        metrics = {
            'accuracy': float(accuracy_score(y_test, y_pred)),
            'f1': float(f1_score(y_test, y_pred, zero_division=0)),
            'precision': float(precision_score(y_test, y_pred, zero_division=0)),
            'recall': float(recall_score(y_test, y_pred, zero_division=0))
        }
        
        return metrics, y_proba
    
    def load_old_metrics(self, timeframe):
        """Load old model metrics"""
        meta_file = self.base_dir / f'metadata_{timeframe}.json'
        
        if not meta_file.exists():
            return None
        
        try:
            with open(meta_file, 'r') as f:
                data = json.load(f)
                return {
                    'f1': float(data.get('f1', 0)),
                    'accuracy': float(data.get('accuracy', 0)),
                    'precision': float(data.get('precision', 0)),
                    'recall': float(data.get('recall', 0))
                }
        except:
            return None
    
    def should_deploy_model(self, old_metrics, new_metrics, timeframe):
        """Determine if new model should be deployed"""
        if old_metrics is None:
            self._log(f"  ✅ {timeframe}: No old model, deploying new one")
            return True
        
        old_f1 = old_metrics.get('f1', 0)
        new_f1 = new_metrics.get('f1', 0)
        improvement = new_f1 - old_f1
        
        if improvement >= self.min_f1_improvement:
            self._log(f"  ✅ {timeframe}: Improvement +{improvement:.4f} F1, DEPLOY NEW MODEL")
            return True
        elif improvement <= self.max_f1_regression:
            self._log(f"  ❌ {timeframe}: Regression {improvement:.4f} F1, keeping old model")
            return False
        else:
            self._log(f"  ⚠️  {timeframe}: Change {improvement:.4f} F1 (≤{self.min_f1_improvement}), keeping old")
            return False
    
    def train_and_evaluate(self, timeframe, best_params):
        """Full train and evaluate pipeline"""
        self._log(f"\n📊 Training {timeframe}...")
        
        # 1. Fetch data
        df = self.fetch_data(timeframe)
        if df is None:
            self._log(f"  ❌ Failed to fetch data")
            return None
        
        # 2. Prepare data
        data, features = self.prepare_data(df)
        if data is None or len(data) < 100:
            self._log(f"  ❌ Insufficient data")
            return None
        
        self._log(f"  ✓ Prepared {len(data)} samples")
        
        # 3. Split (85/15)
        split_idx = int(len(data) * 0.85)
        X_train = data[features].iloc[:split_idx]
        y_train = data['Direction'].iloc[:split_idx]
        X_test = data[features].iloc[split_idx:]
        y_test = data['Direction'].iloc[split_idx:]
        
        # 4. Train model
        new_model = self.train_model(X_train, y_train, best_params)
        self._log(f"  ✓ Model trained")
        
        # 5. Evaluate
        new_metrics, probs = self.evaluate_model(new_model, X_test, y_test)
        self._log(f"  📈 New Metrics - F1: {new_metrics['f1']:.4f}, Prec: {new_metrics['precision']:.4f}, Recall: {new_metrics['recall']:.4f}")
        
        # 6. Compare with old
        old_metrics = self.load_old_metrics(timeframe)
        if old_metrics:
            self._log(f"  📊 Old Metrics - F1: {old_metrics['f1']:.4f}, Prec: {old_metrics['precision']:.4f}")
        
        # 7. Decide
        should_deploy = self.should_deploy_model(old_metrics, new_metrics, timeframe)
        
        # 8. Train calibrator
        calibrator = ModelCalibrator(timeframe)
        calibrator.fit(probs, y_test.values)
        
        return {
            'model': new_model,
            'calibrator': calibrator,
            'metrics': new_metrics,
            'should_deploy': should_deploy,
            'samples': len(data)
        }
    
    def save_models(self, results, timeframe):
        """Save model, calibrator, and metadata"""
        if not results['should_deploy']:
            return
        
        model_file = self.base_dir / f'xgb_{timeframe}.pkl'
        calib_file = self.base_dir / f'calibrator_{timeframe}.pkl'
        meta_file = self.base_dir / f'metadata_{timeframe}.json'
        
        with open(model_file, 'wb') as f:
            pickle.dump(results['model'], f)
        
        with open(calib_file, 'wb') as f:
            pickle.dump(results['calibrator'], f)
        
        metadata = {
            **results['metrics'],
            'trained_at': datetime.now().isoformat(),
            'samples': results['samples'],
            'version': '3.0'
        }
        
        with open(meta_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        self._log(f"  💾 Saved new {timeframe} model")
    
    def run_daily_training(self):
        """Main daily training loop"""
        self._log("\n" + "="*70)
        self._log("🤖 AUTO-TRAINER: Daily Model Update Starting")
        self._log("="*70)
        
        # Backup current models
        self.backup_current_models()
        
        # Load best params from previous training
        with open(self.base_dir / 'best_params.json', 'r') as f:
            all_params = json.load(f)
        
        deployed_count = 0
        results_summary = {}
        
        for timeframe in self.TIMEFRAMES.keys():
            try:
                best_params = all_params.get(timeframe, {})
                if not best_params:
                    self._log(f"❌ No params found for {timeframe}")
                    continue
                
                results = self.train_and_evaluate(timeframe, best_params)
                
                if results and results['should_deploy']:
                    self.save_models(results, timeframe)
                    deployed_count += 1
                    results_summary[timeframe] = 'DEPLOYED ✅'
                elif results:
                    results_summary[timeframe] = 'SKIPPED ⏭️'
                else:
                    results_summary[timeframe] = 'FAILED ❌'
                    
            except Exception as e:
                self._log(f"❌ Error training {timeframe}: {e}")
                results_summary[timeframe] = 'ERROR ❌'
        
        # Summary
        self._log("\n" + "="*70)
        self._log("DAILY TRAINING SUMMARY")
        self._log("="*70)
        for tf, status in results_summary.items():
            self._log(f"{tf:5s}: {status}")
        
        self._log(f"\n✅ Deployed {deployed_count}/{len(self.TIMEFRAMES)} models")
        self._log(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        return deployed_count > 0


def main():
    """Run daily auto-trainer"""
    trainer = AutoTrainer()
    trainer.run_daily_training()


if __name__ == "__main__":
    main()
