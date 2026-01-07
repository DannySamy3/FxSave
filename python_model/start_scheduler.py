#!/usr/bin/env python3
"""
Gold Trading System - Scheduler Launcher for npm run dev
Integrates with Next.js development server to provide live predictions and daily training.

Usage:
    python start_scheduler.py
    
This script:
1. Starts the prediction scheduler in background thread
2. Runs continuous predictions as market data updates
3. Runs daily model training at 5 PM ET
4. Logs all activities
"""

import os
import sys
from pathlib import Path
import time

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Set UTF-8 encoding for console output
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

from scheduler import PredictionScheduler

def main():
    """Start scheduler for app mode"""
    
    print("\n" + "="*70)
    print("GOLD TRADING SYSTEM - SCHEDULER LAUNCHER")
    print("="*70)
    print("\nThis scheduler provides:")
    print("  + Live predictions on candle completion")
    print("  + Daily automatic model training (5 PM ET)")
    print("  + Background thread operation (non-blocking)")
    print("\n" + "="*70 + "\n")
    
    # Create scheduler with training enabled
    scheduler = PredictionScheduler()
    scheduler.enable_retraining = True
    scheduler.retrain_hour = 17  # 5 PM ET
    
    print(f"Configuration:")
    print(f"  Check interval: {scheduler.check_interval}s")
    print(f"  Daily training: Enabled at {scheduler.retrain_hour}:00 (5 PM ET)")
    print(f"  Market awareness: Enabled")
    print()
    
    # Start in background thread (non-blocking)
    try:
        scheduler.start(blocking=False)
        
        print("[OK] Scheduler started in background thread\n")
        print("Target: The scheduler is now running and will:")
        print("  * Update predictions automatically")
        print("  * Retrain models daily at 5 PM ET")
        print("  * Stop when app/main process stops\n")
        
        # Keep main thread alive
        print("Press Ctrl+C to stop the scheduler\n")
        try:
            while scheduler.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping scheduler...")
            scheduler.stop()
            print("[OK] Scheduler stopped")
            
    except Exception as e:
        print(f"[ERROR] Error starting scheduler: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
