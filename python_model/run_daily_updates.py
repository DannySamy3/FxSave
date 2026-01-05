"""
Daily Updates Wrapper Script
Runs CSV update and model learning sequentially.

Designed for Windows Task Scheduler integration.
Handles errors gracefully and provides unified logging.

Usage:
    python run_daily_updates.py [--csv-only] [--model-only] [--force]
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path

from daily_csv_update import update_gold_data_csv
from daily_model_update import daily_model_learning
from update_logger import UpdateLogger


def run_daily_updates(csv_only=False, model_only=False, force=False):
    """
    Run daily CSV update and model learning.
    
    Args:
        csv_only: Only run CSV update
        model_only: Only run model learning
        force: Force update even if already updated today
        
    Returns:
        dict: Combined results
    """
    logger = UpdateLogger()
    base_dir = Path(__file__).parent
    
    print(f"\n{'='*70}")
    print(f"🔄 Daily Updates - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'operation': 'daily_updates',
        'csv_update': None,
        'model_learning': None,
        'overall_status': 'unknown'
    }
    
    csv_success = False
    
    # Step 1: CSV Update
    if not model_only:
        print("📊 Step 1: CSV Update")
        print("-" * 70)
        
        try:
            csv_result = update_gold_data_csv(force=force)
            results['csv_update'] = csv_result
            
            if csv_result['status'] == 'success':
                csv_success = True
                print(f"✅ CSV update successful: {csv_result['rows_added']} rows added\n")
            elif csv_result['status'] == 'skipped':
                print(f"⚠️ CSV update skipped: {csv_result.get('error', 'Already updated today')}\n")
                csv_success = True  # Skipped is OK
            else:
                print(f"❌ CSV update failed: {csv_result.get('error', 'Unknown error')}\n")
                
        except Exception as e:
            print(f"❌ CSV update exception: {e}\n")
            import traceback
            traceback.print_exc()
            results['csv_update'] = {
                'status': 'failed',
                'error': str(e)
            }
    else:
        print("⏭️ Skipping CSV update (--model-only specified)\n")
        csv_success = True  # Assume OK if skipping
    
    # Step 2: Model Learning (only if CSV update succeeded or skipped)
    if not csv_only:
        if csv_success:
            print("🧠 Step 2: Model Learning")
            print("-" * 70)
            
            try:
                model_result = daily_model_learning()
                results['model_learning'] = model_result
                
                if model_result['status'] == 'success':
                    print(f"✅ Model learning successful\n")
                elif model_result['status'] == 'skipped':
                    print(f"⚠️ Model learning skipped: {model_result.get('error', 'No new data')}\n")
                else:
                    print(f"❌ Model learning failed: {model_result.get('error', 'Unknown error')}\n")
                    
            except Exception as e:
                print(f"❌ Model learning exception: {e}\n")
                import traceback
                traceback.print_exc()
                results['model_learning'] = {
                    'status': 'failed',
                    'error': str(e)
                }
        else:
            print("⏭️ Skipping model learning (CSV update failed)\n")
            results['model_learning'] = {
                'status': 'skipped',
                'error': 'CSV update failed, skipping model learning'
            }
    else:
        print("⏭️ Skipping model learning (--csv-only specified)\n")
    
    # Determine overall status
    csv_status = results['csv_update']['status'] if results['csv_update'] else 'skipped'
    model_status = results['model_learning']['status'] if results['model_learning'] else 'skipped'
    
    if csv_status == 'success' and (model_status == 'success' or model_status == 'skipped'):
        results['overall_status'] = 'success'
    elif csv_status == 'failed' or model_status == 'failed':
        results['overall_status'] = 'failed'
    else:
        results['overall_status'] = 'partial'
    
    # Log combined result
    logger.log_update(results)
    
    # Summary
    print("=" * 70)
    print("📋 Summary")
    print("=" * 70)
    print(f"CSV Update:     {csv_status.upper()}")
    if results['model_learning']:
        print(f"Model Learning: {model_status.upper()}")
    print(f"Overall Status: {results['overall_status'].upper()}")
    print("=" * 70)
    
    return results


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Run daily CSV update and model learning',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run both updates
  python run_daily_updates.py
  
  # Force update even if already updated today
  python run_daily_updates.py --force
  
  # Only CSV update
  python run_daily_updates.py --csv-only
  
  # Only model learning
  python run_daily_updates.py --model-only
        """
    )
    
    parser.add_argument('--csv-only', action='store_true',
                        help='Only run CSV update')
    parser.add_argument('--model-only', action='store_true',
                        help='Only run model learning')
    parser.add_argument('--force', action='store_true',
                        help='Force update even if already updated today')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.csv_only and args.model_only:
        print("❌ Error: Cannot specify both --csv-only and --model-only")
        sys.exit(1)
    
    # Run updates
    results = run_daily_updates(
        csv_only=args.csv_only,
        model_only=args.model_only,
        force=args.force
    )
    
    # Exit with error code if failed
    if results['overall_status'] == 'failed':
        sys.exit(1)
    elif results['overall_status'] == 'partial':
        sys.exit(2)  # Partial success
    else:
        sys.exit(0)  # Success


if __name__ == "__main__":
    main()

