"""
Daily Training Scheduler - Runs auto-trainer on schedule
Automatically retrains models each day
Can be run as background service

Features:
- Runs at specified time daily (default: 5 PM after markets close)
- Fetches new day's data
- Retrains all models
- Only deploys if improvements detected
- Keeps log of all training runs
- Email notification on deployment
"""

import schedule
import time
import os
from datetime import datetime
from pathlib import Path
from auto_daily_trainer import AutoTrainer


class DailyScheduler:
    """Manages daily model retraining schedule"""
    
    def __init__(self, run_time='17:00'):
        """
        Initialize scheduler
        
        Args:
            run_time: Time to run daily training (24h format, e.g., '17:00' = 5 PM)
        """
        self.run_time = run_time
        self.trainer = AutoTrainer()
        self.base_dir = Path(__file__).parent
        self.log_file = self.base_dir / 'scheduler.log'
    
    def _log(self, message):
        """Log message"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_msg = f"[{timestamp}] {message}"
        print(log_msg)
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_msg + '\n')
        except Exception as e:
            print(f"Log write error: {e}")
    
    def daily_job(self):
        """Job to run daily"""
        self._log("🌅 Daily training scheduled job starting...")
        try:
            deployed = self.trainer.run_daily_training()
            if deployed:
                self._log("✅ Models deployed successfully")
            else:
                self._log("⏭️ No improvements, models kept as-is")
        except Exception as e:
            self._log(f"❌ Daily training failed: {e}")
    
    def start(self):
        """Start the scheduler"""
        self._log("="*70)
        self._log("🤖 DAILY TRAINING SCHEDULER STARTED")
        self._log(f"Scheduled time: {self.run_time} every day")
        self._log("="*70)
        
        schedule.every().day.at(self.run_time).do(self.daily_job)
        
        self._log(f"✅ Scheduler running. Next run: {self.run_time}")
        
        # Keep scheduler alive
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute


def run_scheduler():
    """Run the scheduler (call this from a background process)"""
    scheduler = DailyScheduler(run_time='17:00')  # 5 PM daily
    scheduler.start()


if __name__ == "__main__":
    run_scheduler()
