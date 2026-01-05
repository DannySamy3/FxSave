"""
Daily CSV Update Script
Appends new market data to gold_data.csv after market close.

Features:
- Fetches latest data from cache or Yahoo Finance
- Appends to gold_data.csv (deduplicates)
- Logs timestamp and row count
- Handles failures gracefully
"""

import pandas as pd
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys

from data_manager import get_data_manager
from update_logger import UpdateLogger


def update_gold_data_csv(timeframe=None, force=False, all_timeframes=True):
    """
    Append today's data to CSV files after market close.
    
    Args:
        timeframe: Specific timeframe to update (None = all timeframes)
        force: Force update even if already updated today
        all_timeframes: If True, update all timeframes separately (multi-timeframe mode)
        
    Returns:
        dict: Update result with status, rows_added per timeframe, timestamp
    """
    logger = UpdateLogger()
    base_dir = Path(__file__).parent
    
    # Multi-timeframe: separate CSVs per timeframe
    timeframes_to_update = ['1d', '4h', '1h', '30m', '15m'] if all_timeframes else [timeframe or '1d']
    
    result = {
        'timestamp': datetime.now().isoformat(),
        'operation': 'csv_update',
        'timeframe': timeframe or 'all',
        'all_timeframes': all_timeframes,
        'status': 'unknown',
        'rows_added': {},
        'last_row_date': {},
        'error': None
    }
    
    try:
        print(f"\n{'='*60}")
        print(f"📊 Daily CSV Update - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        # Check if already updated today
        if not force:
            last_update = logger.get_last_update('csv_update')
            if last_update:
                last_date = datetime.fromisoformat(last_update['timestamp']).date()
                today = datetime.now().date()
                if last_date == today:
                    print(f"  ⚠️ Already updated today ({last_date})")
                    result['status'] = 'skipped'
                    result['error'] = 'Already updated today'
                    return result
        
        # Get data manager
        data_manager = get_data_manager()
        
        total_rows = 0
        
        # Update each timeframe
        for tf in timeframes_to_update:
            print(f"\n  📡 Updating {tf} timeframe...")
            df_new, new_rows_count = data_manager.fetch_incremental_update(tf)
        
            if df_new is None or df_new.empty:
                print(f"     ⚠️ No data available for {tf}")
                result['rows_added'][tf] = 0
                result['last_row_date'][tf] = None
                continue
            
            # Data manager already saves to cache, so we just track the update
            result['rows_added'][tf] = new_rows_count
            if not df_new.empty:
                result['last_row_date'][tf] = df_new.index[-1].strftime('%Y-%m-%d')
            else:
                result['last_row_date'][tf] = None
            
            total_rows += new_rows_count
            print(f"     ✓ {tf}: {new_rows_count} new rows, "
                  f"last: {result['last_row_date'][tf]}")
        
        # Also maintain legacy gold_data.csv for backward compatibility (D1 only)
        if '1d' in timeframes_to_update:
            legacy_path = base_dir / 'gold_data.csv'
            df_d1 = data_manager.get_cached_data('1d')
            if df_d1 is not None and not df_d1.empty:
                print(f"\n  💾 Updating legacy gold_data.csv (D1 data)...")
                df_d1.to_csv(legacy_path)
                print(f"     ✓ Legacy CSV updated: {len(df_d1)} rows")
        
        # Update result
        result['status'] = 'success' if total_rows > 0 else 'no_new_data'
        result['total_rows_added'] = total_rows
        
        print(f"\n  ✅ CSV update complete: {total_rows} total new rows across all timeframes")
        
        # Log the update
        logger.log_update(result)
        
        return result
        
    except Exception as e:
        print(f"  ❌ Error updating CSV: {e}")
        import traceback
        traceback.print_exc()
        
        result['status'] = 'failed'
        result['error'] = str(e)
        logger.log_update(result)
        
        return result


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Daily CSV Update')
    parser.add_argument('--timeframe', '-t', type=str, default=None,
                        help='Specific timeframe to update (default: all)')
    parser.add_argument('--force', action='store_true',
                        help='Force update even if already updated today')
    parser.add_argument('--single-timeframe', action='store_true',
                        help='Update only specified timeframe (not all)')
    
    args = parser.parse_args()
    
    result = update_gold_data_csv(
        timeframe=args.timeframe, 
        force=args.force,
        all_timeframes=not args.single_timeframe
    )
    
    # Exit with error code if failed
    if result['status'] == 'failed':
        sys.exit(1)
    
    print(f"\n✅ CSV update complete")
    return result


if __name__ == "__main__":
    main()

