"""
Continuous Scheduler - Always-Running Daily Update Automation
Runs continuously and executes CSV updates and model retraining after market close.

Features:
- Runs continuously in background
- Monitors market close time
- Executes CSV update and model retraining automatically
- Full logging and error handling
- Can be run as Windows service or background process
"""

import time
import threading
from datetime import datetime, timedelta
import sys
import signal
from pathlib import Path
import json

from daily_csv_update import update_gold_data_csv
from daily_model_update import daily_model_learning
from update_logger import UpdateLogger


class ContinuousScheduler:
    """
    Continuous scheduler that runs always and executes daily updates
    after market close.
    """
    
    # Gold market close time (Friday 5 PM ET / 17:00 ET)
    # Convert to local time - adjust as needed
    MARKET_CLOSE_HOUR = 17  # 5 PM ET
    MARKET_CLOSE_MINUTE = 0
    
    # Check interval (seconds) - check every minute
    CHECK_INTERVAL = 60
    
    def __init__(self, config=None):
        """
        Initialize continuous scheduler.
        
        Args:
            config: Optional config dict with scheduling settings
        """
        self.logger = UpdateLogger()
        self.running = False
        self._stop_event = threading.Event()
        self._scheduler_thread = None
        
        # Load config if provided
        if config:
            self.market_close_hour = config.get('market_close_hour', self.MARKET_CLOSE_HOUR)
            self.market_close_minute = config.get('market_close_minute', self.MARKET_CLOSE_MINUTE)
            self.check_interval = config.get('check_interval', self.CHECK_INTERVAL)
        else:
            self.market_close_hour = self.MARKET_CLOSE_HOUR
            self.market_close_minute = self.MARKET_CLOSE_MINUTE
            self.check_interval = self.CHECK_INTERVAL
        
        # Track execution state
        self.last_execution_date = None
        self.execution_count = 0
        self.error_count = 0
        
        # Load last execution date from log
        self._load_last_execution()
    
    def _load_last_execution(self):
        """Load last execution date from update logs"""
        try:
            last_csv = self.logger.get_last_update('csv_update')
            if last_csv and last_csv.get('status') == 'success':
                last_date = datetime.fromisoformat(last_csv['timestamp']).date()
                self.last_execution_date = last_date
        except Exception as e:
            print(f"  ⚠️ Could not load last execution date: {e}")
    
    def is_market_closed(self):
        """
        Check if market has closed for the day.
        Gold market closes Friday 5 PM ET, reopens Sunday 6 PM ET.
        """
        now = datetime.now()
        
        # Friday after market close
        if now.weekday() == 4:  # Friday
            if now.hour >= self.market_close_hour:
                return True
        
        # Saturday (market closed)
        if now.weekday() == 5:
            return True
        
        # Sunday before market open
        if now.weekday() == 6:
            if now.hour < 18:  # Before 6 PM ET
                return True
        
        return False
    
    def should_execute_daily_updates(self):
        """
        Determine if daily updates should be executed.
        Executes once per day after market close.
        """
        now = datetime.now()
        today = now.date()
        
        # Don't execute if already executed today
        if self.last_execution_date == today:
            return False
        
        # Only execute after market close
        if not self.is_market_closed():
            return False
        
        # Execute if it's Friday after close, or Saturday, or Sunday before open
        # But only once per day
        if now.weekday() == 4:  # Friday
            if now.hour >= self.market_close_hour:
                return True
        elif now.weekday() == 5:  # Saturday
            return True
        elif now.weekday() == 6:  # Sunday
            if now.hour < 18:
                return True
        
        return False
    
    def execute_daily_updates(self):
        """
        Execute daily CSV update and model retraining.
        """
        print(f"\n{'='*70}")
        print(f"🔄 EXECUTING DAILY UPDATES - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")
        
        try:
            # Step 1: CSV Update
            print("📊 Step 1: CSV Update")
            print("-" * 70)
            csv_result = update_gold_data_csv()
            
            if csv_result['status'] != 'success':
                print(f"❌ CSV update failed: {csv_result.get('error', 'Unknown error')}")
                self.error_count += 1
                return False
            
            print(f"✅ CSV update successful: {csv_result['rows_added']} rows added\n")
            
            # Step 2: Model Retraining (only if CSV update succeeded)
            print("🧠 Step 2: Model Retraining")
            print("-" * 70)
            model_result = daily_model_learning()
            
            if model_result['status'] != 'success':
                print(f"⚠️ Model retraining skipped/failed: {model_result.get('error', 'Unknown error')}")
                # Don't count as error if skipped due to no new data
                if model_result['status'] == 'failed':
                    self.error_count += 1
            
            print(f"✅ Daily updates complete\n")
            
            # Update tracking
            self.last_execution_date = datetime.now().date()
            self.execution_count += 1
            
            return True
            
        except Exception as e:
            print(f"❌ Error executing daily updates: {e}")
            import traceback
            traceback.print_exc()
            self.error_count += 1
            return False
    
    def _scheduler_loop(self):
        """Main scheduler loop (runs in background thread)"""
        print(f"🚀 Continuous Scheduler Started")
        print(f"   Check interval: {self.check_interval}s")
        print(f"   Market close: {self.market_close_hour:02d}:{self.market_close_minute:02d}")
        print(f"   Last execution: {self.last_execution_date or 'Never'}")
        print(f"{'='*70}\n")
        
        while not self._stop_event.is_set():
            try:
                # Check if we should execute daily updates
                if self.should_execute_daily_updates():
                    self.execute_daily_updates()
                else:
                    # Log status periodically (every hour)
                    now = datetime.now()
                    if now.minute == 0:
                        print(f"⏰ {now.strftime('%Y-%m-%d %H:%M:%S')} - Scheduler running "
                              f"(Last execution: {self.last_execution_date or 'Never'}, "
                              f"Executions: {self.execution_count}, Errors: {self.error_count})")
                
            except Exception as e:
                print(f"❌ Scheduler error: {e}")
                import traceback
                traceback.print_exc()
                self.error_count += 1
            
            # Wait for next check
            self._stop_event.wait(self.check_interval)
        
        print("🛑 Continuous Scheduler Stopped")
    
    def start(self, blocking=True):
        """
        Start the continuous scheduler.
        
        Args:
            blocking: If True, blocks main thread. If False, runs in background.
        """
        if self.running:
            print("⚠️ Scheduler already running")
            return
        
        self.running = True
        self._stop_event.clear()
        
        print("=" * 70)
        print("🏁 CONTINUOUS DAILY UPDATE SCHEDULER")
        print(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Mode: {'Blocking' if blocking else 'Background'}")
        print("=" * 70)
        
        if blocking:
            # Run in main thread
            try:
                self._scheduler_loop()
            except KeyboardInterrupt:
                self.stop()
        else:
            # Run in background thread
            self._scheduler_thread = threading.Thread(
                target=self._scheduler_loop,
                daemon=False,  # Non-daemon so it keeps running
                name="ContinuousScheduler"
            )
            self._scheduler_thread.start()
            print("📋 Scheduler running in background thread")
    
    def stop(self):
        """Stop the scheduler"""
        print("\n⏹️ Stopping continuous scheduler...")
        self._stop_event.set()
        self.running = False
        
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=10)
        
        print("✅ Scheduler stopped")
    
    def get_status(self):
        """Get scheduler status"""
        return {
            "running": self.running,
            "last_execution_date": str(self.last_execution_date) if self.last_execution_date else None,
            "execution_count": self.execution_count,
            "error_count": self.error_count,
            "market_closed": self.is_market_closed(),
            "check_interval": self.check_interval,
            "next_check": datetime.now() + timedelta(seconds=self.check_interval)
        }


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\n⏹️ Interrupt received, shutting down scheduler...")
    sys.exit(0)


def main():
    """Main entry point for continuous scheduler"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Continuous Daily Update Scheduler',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run in foreground (blocking)
  python continuous_scheduler.py
  
  # Run in background (non-blocking)
  python continuous_scheduler.py --background
  
  # Check status
  python continuous_scheduler.py --status
        """
    )
    
    parser.add_argument('--background', action='store_true',
                        help='Run in background thread (non-blocking)')
    parser.add_argument('--status', action='store_true',
                        help='Show status and exit')
    parser.add_argument('--check-interval', type=int, default=60,
                        help='Check interval in seconds (default: 60)')
    parser.add_argument('--market-close-hour', type=int, default=17,
                        help='Market close hour (default: 17 for 5 PM ET)')
    parser.add_argument('--market-close-minute', type=int, default=0,
                        help='Market close minute (default: 0)')
    
    args = parser.parse_args()
    
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create scheduler
    config = {
        'check_interval': args.check_interval,
        'market_close_hour': args.market_close_hour,
        'market_close_minute': args.market_close_minute
    }
    scheduler = ContinuousScheduler(config)
    
    if args.status:
        status = scheduler.get_status()
        print("\n📊 Scheduler Status:")
        print(json.dumps(status, indent=2, default=str))
        return
    
    # Start scheduler
    try:
        scheduler.start(blocking=not args.background)
        
        # If running in background, keep main thread alive
        if args.background:
            print("\n✅ Scheduler running in background. Press Ctrl+C to stop.")
            try:
                while scheduler.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                scheduler.stop()
        
    except KeyboardInterrupt:
        scheduler.stop()


if __name__ == "__main__":
    main()

