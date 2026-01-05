"""
Daily Model Learning Script
Updates models with new daily data after market close.

Features:
- Checks for new data availability
- Runs incremental learning or full retrain
- Logs training metrics and timestamps
- Handles failures gracefully
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
import sys

from data_manager import get_data_manager
from rolling_retrain import RollingRetrainer
from update_logger import UpdateLogger


def daily_model_learning(timeframe=None, full_retrain=False, min_new_rows=1, multi_timeframe_mode=True):
    """
    Update models with new daily data.
    
    Args:
        timeframe: Specific timeframe to update (None = all timeframes)
        full_retrain: If True, run full retrain; if False, check if incremental needed
        min_new_rows: Minimum new rows required to trigger learning
        multi_timeframe_mode: If True, retrain D1 and H4/H1 independently (multi-timeframe architecture)
        
    Returns:
        dict: Learning result with status, metrics, timestamp
    """
    logger = UpdateLogger()
    base_dir = Path(__file__).parent
    
    result = {
        'timestamp': datetime.now().isoformat(),
        'operation': 'model_learning',
        'timeframe': timeframe or 'all',
        'mode': 'full_retrain' if full_retrain else 'incremental',
        'status': 'unknown',
        'metrics': {},
        'rows_processed': 0,
        'error': None
    }
    
    try:
        print(f"\n{'='*60}")
        print(f"🧠 Daily Model Learning - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        # Get data manager
        data_manager = get_data_manager()
        
        # Determine which timeframes to train
        if multi_timeframe_mode:
            # Multi-timeframe architecture: train D1, H4, H1 independently
            if timeframe:
                timeframes_to_train = [timeframe]
            else:
                # Train D1 (bias), H4 and H1 (confirmation) independently
                timeframes_to_train = ['1d', '4h', '1h']
        else:
            # Legacy mode: train all timeframes
            timeframes_to_train = [timeframe] if timeframe else ['15m', '30m', '1h', '4h', '1d']
        
        # Check for new data
        if not full_retrain:
            print(f"  🔍 Checking for new data...")
            new_data_available = False
            total_new_rows = 0
            
            timeframes_to_check = timeframes_to_train
            
            for tf in timeframes_to_check:
                try:
                    _, new_rows = data_manager.fetch_incremental_update(tf)
                    if new_rows >= min_new_rows:
                        new_data_available = True
                        total_new_rows += new_rows
                        print(f"     {tf}: {new_rows} new rows")
                except Exception as e:
                    print(f"     ⚠️ Error checking {tf}: {e}")
            
            if not new_data_available:
                print(f"  ⚠️ No new data available (minimum {min_new_rows} rows required)")
                result['status'] = 'skipped'
                result['error'] = 'No new data available'
                logger.log_update(result)
                return result
            
            result['rows_processed'] = total_new_rows
            print(f"  ✓ Found {total_new_rows} new rows across timeframes")
        
        # Initialize retrainer
        print(f"  🔧 Initializing retrainer...")
        retrainer = RollingRetrainer()
        
        # Run retraining
        if timeframe:
            # Single timeframe
            print(f"  🎯 Training {timeframe} only...")
            data, feature_cols = retrainer.get_training_data(timeframe)
            
            if data is None:
                result['status'] = 'failed'
                result['error'] = f'Insufficient data for {timeframe}'
                logger.log_update(result)
                return result
            
            model, calibrator, metrics = retrainer.train_single_timeframe(
                timeframe, data, feature_cols
            )
            retrainer.save_artifacts(timeframe, model, calibrator)
            
            result['metrics'][timeframe] = metrics
            result['status'] = 'success'
            
        else:
            # Multiple timeframes (D1, H4, H1 in multi-timeframe mode)
            print(f"  🎯 Training timeframes: {', '.join(timeframes_to_train)}...")
            
            for tf in timeframes_to_train:
                print(f"\n  📊 Training {tf}...")
                try:
                    data, feature_cols = retrainer.get_training_data(tf)
                    
                    if data is None:
                        print(f"     ⚠️ Insufficient data for {tf}, skipping")
                        continue
                    
                    model, calibrator, metrics = retrainer.train_single_timeframe(
                        tf, data, feature_cols
                    )
                    retrainer.save_artifacts(tf, model, calibrator)
                    
                    result['metrics'][tf] = metrics
                    print(f"     ✅ {tf} complete: Accuracy {metrics.get('accuracy', 0):.2%}")
                    
                except Exception as e:
                    print(f"     ❌ Error training {tf}: {e}")
                    import traceback
                    traceback.print_exc()
            
            if result['metrics']:
                result['status'] = 'success'
            else:
                result['status'] = 'failed'
                result['error'] = 'No timeframes trained successfully'
        
        # Log the update
        logger.log_update(result)
        
        print(f"\n  ✅ Model learning complete")
        print(f"     Timeframes updated: {len(result['metrics'])}")
        for tf, m in result['metrics'].items():
            print(f"       {tf}: Accuracy {m.get('accuracy', 0):.2%}, "
                  f"Train={m.get('n_train', 0)}, Test={m.get('n_test', 0)}")
        
        return result
        
    except Exception as e:
        print(f"  ❌ Error in model learning: {e}")
        import traceback
        traceback.print_exc()
        
        result['status'] = 'failed'
        result['error'] = str(e)
        logger.log_update(result)
        
        return result


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Daily Model Learning')
    parser.add_argument('--timeframe', '-t', type=str, default=None,
                        help='Specific timeframe to update (default: all)')
    parser.add_argument('--full-retrain', action='store_true',
                        help='Force full retrain even if no new data')
    parser.add_argument('--min-rows', type=int, default=1,
                        help='Minimum new rows required (default: 1)')
    parser.add_argument('--legacy-mode', action='store_true',
                        help='Use legacy mode (train all timeframes)')
    
    args = parser.parse_args()
    
    result = daily_model_learning(
        timeframe=args.timeframe,
        full_retrain=args.full_retrain,
        min_new_rows=args.min_rows,
        multi_timeframe_mode=not args.legacy_mode
    )
    
    # Exit with error code if failed
    if result['status'] == 'failed':
        sys.exit(1)
    
    print(f"\n✅ Model learning complete")
    return result


if __name__ == "__main__":
    main()

