"""
Calibration Drift Monitoring Script
Checks forward test log for excessive calibration drift warnings.
"""

import pandas as pd
import os
from pathlib import Path
from datetime import datetime, timedelta

def monitor_calibration_drift(log_path="forward_test_log.csv", lookback_hours=24, threshold=0.15):
    """
    Monitor calibration drift from forward test log.
    
    Args:
        log_path: Path to forward test log
        lookback_hours: Hours to look back
        threshold: Drift threshold (0.15 = 15%)
    """
    log_file = Path(__file__).parent / log_path
    
    if not log_file.exists():
        print(f"Log file not found: {log_file}")
        print("Run predictions first to generate log data.")
        return
    
    try:
        df = pd.read_csv(log_file, encoding='utf-8')
        
        if df.empty:
            print("Log file is empty. Run predictions first.")
            return
        
        # Parse timestamp
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Filter to lookback period
        cutoff = datetime.now() - timedelta(hours=lookback_hours)
        df_recent = df[df['timestamp'] >= cutoff]
        
        if df_recent.empty:
            print(f"No data in last {lookback_hours} hours.")
            return
        
        print("=" * 70)
        print("CALIBRATION DRIFT MONITORING")
        print("=" * 70)
        print(f"Period: Last {lookback_hours} hours")
        print(f"Total signals: {len(df_recent)}")
        print(f"Drift threshold: {threshold * 100:.0f}%")
        print("=" * 70)
        print()
        
        # Calculate drift (absolute difference between raw and calibrated)
        df_recent['drift_abs'] = abs(df_recent['raw_conf'] - df_recent['calib_conf'])
        df_recent['drift_pct'] = df_recent['drift_abs'] * 100
        
        # Find excessive drift
        excessive = df_recent[df_recent['drift_abs'] > threshold]
        
        if len(excessive) > 0:
            print(f"⚠️  EXCESSIVE DRIFT DETECTED: {len(excessive)} signals")
            print("-" * 70)
            
            # Group by timeframe
            by_tf = excessive.groupby('timeframe').agg({
                'drift_pct': ['mean', 'max', 'count']
            }).round(2)
            
            print("\nBy Timeframe:")
            print(by_tf.to_string())
            
            # Show worst cases
            print("\nWorst Cases (Top 10):")
            worst = excessive.nlargest(10, 'drift_abs')[['timestamp', 'timeframe', 'raw_conf', 'calib_conf', 'drift_pct']]
            worst['raw_conf'] = (worst['raw_conf'] * 100).round(2)
            worst['calib_conf'] = (worst['calib_conf'] * 100).round(2)
            print(worst.to_string(index=False))
            
            # Recommendations
            print("\n" + "=" * 70)
            print("RECOMMENDATIONS:")
            print("=" * 70)
            
            problematic_tfs = by_tf[by_tf[('drift_pct', 'mean')] > threshold * 100].index.tolist()
            if problematic_tfs:
                print(f"⚠️  Retrain models for: {', '.join(problematic_tfs)}")
                print("   Command: python train.py")
            
        else:
            print("✓ No excessive drift detected")
            print(f"  Max drift: {df_recent['drift_pct'].max():.2f}%")
            print(f"  Mean drift: {df_recent['drift_pct'].mean():.2f}%")
        
        # Overall statistics
        print("\n" + "=" * 70)
        print("OVERALL STATISTICS")
        print("=" * 70)
        
        stats = df_recent.groupby('timeframe').agg({
            'drift_pct': ['mean', 'std', 'max', 'min'],
            'raw_conf': 'mean',
            'calib_conf': 'mean'
        }).round(2)
        
        print(stats.to_string())
        
        # Summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Signals analyzed: {len(df_recent)}")
        print(f"Excessive drift: {len(excessive)} ({len(excessive)/len(df_recent)*100:.1f}%)")
        print(f"Mean drift: {df_recent['drift_pct'].mean():.2f}%")
        print(f"Max drift: {df_recent['drift_pct'].max():.2f}%")
        
    except Exception as e:
        print(f"Error analyzing log: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import sys
    
    lookback = 24
    if len(sys.argv) > 1:
        try:
            lookback = int(sys.argv[1])
        except:
            pass
    
    monitor_calibration_drift(lookback_hours=lookback)








