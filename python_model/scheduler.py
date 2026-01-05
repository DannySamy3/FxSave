"""
Prediction Scheduler - Automated Rolling Predictions
Runs predictions automatically on candle completion times.

Features:
- Market hours awareness (Gold trades ~23h/day)
- Timeframe-specific scheduling
- Graceful error handling
- Configurable intervals
- Optional retraining schedule
"""

import time
import threading
import schedule
from datetime import datetime, timedelta
import sys
import signal
import json
from pathlib import Path

from live_predictor import LivePredictor
from data_manager import get_data_manager


def load_config():
    """Load configuration"""
    path = Path(__file__).parent / 'config.json'
    with open(path, 'r') as f:
        return json.load(f)


class PredictionScheduler:
    """
    Automated scheduler for live predictions.
    Triggers predictions based on candle completion times.
    """
    
    # Gold market hours (approximate - trades 23h/day Sunday-Friday)
    MARKET_OPEN_HOUR = 18    # Sunday 6 PM ET
    MARKET_CLOSE_HOUR = 17   # Friday 5 PM ET
    
    def __init__(self, config=None):
        """
        Initialize scheduler.
        
        Args:
            config: Configuration dict
        """
        self.config = config or load_config()
        self.predictor = None  # Lazy load
        self.data_manager = get_data_manager()
        
        self.running = False
        self.last_prediction_time = {}
        self.prediction_count = 0
        self.error_count = 0
        
        # Scheduler settings
        self.check_interval = 60  # Check every 60 seconds
        self.enable_retraining = False
        self.retrain_day = 'sunday'  # Weekly retraining
        self.retrain_hour = 18  # 6 PM
        
        # Thread for background running
        self._scheduler_thread = None
        self._stop_event = threading.Event()
    
    def _get_predictor(self):
        """Lazy load predictor"""
        if self.predictor is None:
            print("🔧 Initializing predictor...")
            self.predictor = LivePredictor(self.config)
        return self.predictor
    
    def is_market_open(self):
        """
        Check if Gold market is likely open.
        Gold trades nearly 24h but closed on weekends.
        """
        now = datetime.now()
        
        # Closed on Saturday
        if now.weekday() == 5:  # Saturday
            return False
        
        # Sunday - opens at 6 PM ET (approximate)
        if now.weekday() == 6 and now.hour < 18:
            return False
        
        # Friday - closes at 5 PM ET (approximate)
        if now.weekday() == 4 and now.hour >= 17:
            return False
        
        return True
    
    def should_predict(self, timeframe):
        """
        Determine if we should run a prediction for this timeframe.
        Based on candle completion times.
        """
        now = datetime.now()
        
        # Check market hours
        if not self.is_market_open():
            return False
        
        # Get last prediction time
        last_time = self.last_prediction_time.get(timeframe)
        
        # Candle intervals in minutes
        intervals = {
            '15m': 15,
            '30m': 30,
            '1h': 60,
            '4h': 240,
            '1d': 1440
        }
        
        interval_mins = intervals.get(timeframe, 60)
        
        # Check if enough time has passed
        if last_time:
            elapsed = (now - last_time).total_seconds() / 60
            if elapsed < interval_mins * 0.9:  # 90% of interval
                return False
        
        # Check if we're near a candle boundary
        minute = now.minute
        hour = now.hour
        
        if timeframe == '15m':
            # Predict at :00, :15, :30, :45
            return minute % 15 < 2
        
        elif timeframe == '30m':
            # Predict at :00, :30
            return minute % 30 < 2
        
        elif timeframe == '1h':
            # Predict at :00
            return minute < 3
        
        elif timeframe == '4h':
            # Predict at 4h boundaries
            return minute < 5 and hour % 4 == 0
        
        elif timeframe == '1d':
            # Predict once per day (around market open)
            return minute < 5 and hour == 18
        
        return False
    
    def run_prediction_cycle(self):
        """
        Run a full prediction cycle for all timeframes that need updating.
        """
        print(f"\n{'='*50}")
        print(f"⏰ Scheduler Check: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*50}")
        
        if not self.is_market_open():
            print("💤 Market closed - skipping")
            return
        
        predictor = self._get_predictor()
        
        # Check which timeframes need prediction
        timeframes_to_update = []
        
        for tf in LivePredictor.TF_HIERARCHY:
            if self.should_predict(tf):
                timeframes_to_update.append(tf)
        
        if not timeframes_to_update:
            print("✓ All timeframes up to date")
            return
        
        print(f"📊 Updating: {', '.join(timeframes_to_update)}")
        
        try:
            # Run full prediction (respects HTF hierarchy)
            results = predictor.predict_all_timeframes(update_data=True)
            
            # Update tracking
            now = datetime.now()
            for tf in timeframes_to_update:
                self.last_prediction_time[tf] = now
            
            self.prediction_count += 1
            
            # Summary
            print(f"\n✅ Prediction #{self.prediction_count} complete")
            
            # Print quick summary
            for tf in LivePredictor.TF_HIERARCHY:
                if tf in results:
                    r = results[tf]
                    icon = "✅" if r.get('decision') == 'TRADE' else "⛔"
                    print(f"  {tf}: {icon} {r.get('direction', 'N/A')} ({r.get('confidence', 0):.1f}%)")
            
        except Exception as e:
            self.error_count += 1
            print(f"❌ Prediction error: {e}")
            import traceback
            traceback.print_exc()
    
    def run_retraining(self):
        """
        Run scheduled retraining (weekly).
        """
        if not self.enable_retraining:
            return
        
        print(f"\n{'='*50}")
        print("🔄 SCHEDULED RETRAINING")
        print(f"{'='*50}")
        
        try:
            # Import and run training
            from train import main as train_main
            train_main()
            
            # Reload predictor with new models
            self.predictor = None  # Force reload
            print("✅ Retraining complete")
            
        except Exception as e:
            print(f"❌ Retraining failed: {e}")
    
    def _scheduler_loop(self):
        """Main scheduler loop (runs in background thread)"""
        print(f"🚀 Scheduler started - checking every {self.check_interval}s")
        
        while not self._stop_event.is_set():
            try:
                self.run_prediction_cycle()
            except Exception as e:
                print(f"❌ Scheduler error: {e}")
            
            # Wait for next check
            self._stop_event.wait(self.check_interval)
        
        print("🛑 Scheduler stopped")
    
    def start(self, blocking=True):
        """
        Start the scheduler.
        
        Args:
            blocking: If True, blocks main thread. If False, runs in background.
        """
        self.running = True
        self._stop_event.clear()
        
        print("=" * 60)
        print("🏁 GOLD PREDICTION SCHEDULER")
        print(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Check interval: {self.check_interval}s")
        print(f"   Retraining: {'Enabled' if self.enable_retraining else 'Disabled'}")
        print("=" * 60)
        
        if blocking:
            # Run in main thread
            self._scheduler_loop()
        else:
            # Run in background thread
            self._scheduler_thread = threading.Thread(
                target=self._scheduler_loop,
                daemon=True
            )
            self._scheduler_thread.start()
            print("📋 Scheduler running in background")
    
    def stop(self):
        """Stop the scheduler"""
        print("\n⏹️ Stopping scheduler...")
        self._stop_event.set()
        self.running = False
        
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=5)
    
    def get_status(self):
        """Get scheduler status"""
        return {
            "running": self.running,
            "prediction_count": self.prediction_count,
            "error_count": self.error_count,
            "last_predictions": self.last_prediction_time,
            "market_open": self.is_market_open(),
            "check_interval": self.check_interval
        }


class SimpleCronScheduler:
    """
    Simple cron-like scheduler using the schedule library.
    Alternative to the thread-based scheduler.
    """
    
    def __init__(self):
        self.predictor = None
        self.running = False
    
    def _get_predictor(self):
        if self.predictor is None:
            self.predictor = LivePredictor()
        return self.predictor
    
    def run_prediction(self):
        """Job to run predictions"""
        try:
            predictor = self._get_predictor()
            predictor.predict_all_timeframes(update_data=True)
        except Exception as e:
            print(f"❌ Prediction error: {e}")
    
    def setup_schedule(self):
        """Setup prediction schedule"""
        
        # 15m predictions - every 15 minutes
        schedule.every(15).minutes.do(self.run_prediction)
        
        # Or more specific times:
        # schedule.every().hour.at(":00").do(self.run_prediction)
        # schedule.every().hour.at(":15").do(self.run_prediction)
        # schedule.every().hour.at(":30").do(self.run_prediction)
        # schedule.every().hour.at(":45").do(self.run_prediction)
        
        print("📅 Schedule configured")
    
    def run(self):
        """Run the scheduler"""
        self.setup_schedule()
        self.running = True
        
        print("🚀 Cron scheduler started")
        print("   Press Ctrl+C to stop")
        
        while self.running:
            schedule.run_pending()
            time.sleep(1)


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\n⏹️ Interrupt received, shutting down...")
    sys.exit(0)


def main():
    """Main entry point for scheduler"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Gold Prediction Scheduler')
    parser.add_argument('--interval', type=int, default=60,
                        help='Check interval in seconds (default: 60)')
    parser.add_argument('--once', action='store_true',
                        help='Run once and exit')
    parser.add_argument('--retrain', action='store_true',
                        help='Enable weekly retraining')
    parser.add_argument('--cron', action='store_true',
                        help='Use cron-style scheduler')
    
    args = parser.parse_args()
    
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    if args.once:
        # Single prediction run
        from live_predictor import run_live_prediction
        run_live_prediction()
        return
    
    if args.cron:
        # Use cron-style scheduler
        scheduler = SimpleCronScheduler()
        scheduler.run()
    else:
        # Use thread-based scheduler
        scheduler = PredictionScheduler()
        scheduler.check_interval = args.interval
        scheduler.enable_retraining = args.retrain
        
        try:
            scheduler.start(blocking=True)
        except KeyboardInterrupt:
            scheduler.stop()


if __name__ == "__main__":
    main()






