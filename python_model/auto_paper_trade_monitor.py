"""
Gold-Trade Pro v2.2.0 - Automated Paper Trading + Drift Monitor + Integrity Checker

Usage: python auto_paper_trade_monitor.py

Features:
1. Starts paper trading (--paper_trade) in the background
2. Monitors calibration drift at configurable intervals
3. Verifies system integrity at configurable intervals
4. Runs all steps concurrently and logs output
"""

import subprocess
import time
import threading
import sys
import os
from datetime import datetime
from pathlib import Path

# CONFIGURATION
PAPER_TRADE_DURATION = "24h"   # Paper trading duration
PAPER_TRADE_INTERVAL = 300     # Interval in seconds for prediction cycle
DRIFT_CHECK_INTERVAL = 1800    # Check calibration drift every 30 minutes
INTEGRITY_CHECK_INTERVAL = 3600 # Verify system integrity every 60 minutes

# COMMANDS (run from python_model directory)
BASE_DIR = Path(__file__).parent
PAPER_TRADE_CMD = [
    sys.executable, 
    str(BASE_DIR / "live_predictor.py"),
    "--paper_trade",
    "--duration", PAPER_TRADE_DURATION,
    "--interval", str(PAPER_TRADE_INTERVAL)
]
DRIFT_MONITOR_CMD = [sys.executable, str(BASE_DIR / "monitor_calibration_drift.py")]
INTEGRITY_CHECK_CMD = [sys.executable, str(BASE_DIR / "verify_system_integrity.py")]

# Logging
LOG_FILE = BASE_DIR / "auto_monitor.log"
log_lock = threading.Lock()

def log(message, level="INFO"):
    """Thread-safe logging to both console and file"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_message = f"[{timestamp}] [{level}] {message}"
    
    with log_lock:
        print(log_message)
        try:
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(log_message + '\n')
        except Exception as e:
            print(f"[ERROR] Failed to write to log: {e}")

def run_command(cmd, description, capture_output=False):
    """
    Run a subprocess command and handle output.
    
    Args:
        cmd: Command as list or string
        description: Description for logging
        capture_output: If True, capture and log output
        
    Returns:
        subprocess.Popen process object
    """
    try:
        log(f"Starting: {description}")
        
        if capture_output:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(BASE_DIR)
            )
        else:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(BASE_DIR)
            )
        
        log(f"Started: {description} (PID: {process.pid})")
        return process
        
    except Exception as e:
        log(f"Failed to start {description}: {e}", "ERROR")
        return None

def run_command_and_log_output(cmd, description):
    """
    Run a command, capture output, and log it.
    Used for drift monitoring and integrity checks.
    """
    try:
        log(f"Running: {description}")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(BASE_DIR)
        )
        
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            log(f"Completed: {description}")
            if stdout:
                # Log important lines only
                for line in stdout.split('\n'):
                    if line.strip() and ('✓' in line or '✗' in line or '⚠' in line or 'ERROR' in line.upper()):
                        log(f"  {line.strip()}", "OUTPUT")
        else:
            log(f"Failed: {description} (exit code: {process.returncode})", "ERROR")
            if stderr:
                log(f"  Error: {stderr[:500]}", "ERROR")
        
        return process.returncode == 0
        
    except Exception as e:
        log(f"Exception running {description}: {e}", "ERROR")
        return False

def periodic_task(cmd, description, interval, initial_delay=0):
    """
    Run a command periodically in a separate thread.
    
    Args:
        cmd: Command to run
        description: Description for logging
        interval: Interval in seconds
        initial_delay: Initial delay before first run
    """
    if initial_delay > 0:
        log(f"{description} will start in {initial_delay} seconds...")
        time.sleep(initial_delay)
    
    cycle = 0
    while True:
        cycle += 1
        log(f"{description} - Cycle {cycle}")
        run_command_and_log_output(cmd, description)
        log(f"Next {description} check in {interval} seconds...")
        time.sleep(interval)

def main():
    """Main function to orchestrate paper trading and monitoring"""
    print("=" * 70)
    print("Gold-Trade Pro v2.2.0 - Automated Paper Trading + Monitoring")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("Configuration:")
    print(f"  Paper Trading Duration: {PAPER_TRADE_DURATION}")
    print(f"  Prediction Interval: {PAPER_TRADE_INTERVAL} seconds")
    print(f"  Drift Check Interval: {DRIFT_CHECK_INTERVAL} seconds ({DRIFT_CHECK_INTERVAL/60:.0f} minutes)")
    print(f"  Integrity Check Interval: {INTEGRITY_CHECK_INTERVAL} seconds ({INTEGRITY_CHECK_INTERVAL/60:.0f} minutes)")
    print()
    print("=" * 70)
    print()
    
    # Initialize log file
    log("=" * 70)
    log("Automated Paper Trading Monitor Started")
    log("=" * 70)
    
    # Verify scripts exist
    scripts = {
        "live_predictor.py": BASE_DIR / "live_predictor.py",
        "monitor_calibration_drift.py": BASE_DIR / "monitor_calibration_drift.py",
        "verify_system_integrity.py": BASE_DIR / "verify_system_integrity.py"
    }
    
    missing = []
    for name, path in scripts.items():
        if not path.exists():
            missing.append(name)
    
    if missing:
        log(f"ERROR: Missing required scripts: {', '.join(missing)}", "ERROR")
        sys.exit(1)
    
    log("All required scripts found")
    
    # 1. Start paper trading in background
    log("Starting paper trading session...")
    paper_trade_process = run_command(
        PAPER_TRADE_CMD,
        "Paper trading session",
        capture_output=False
    )
    
    if paper_trade_process is None:
        log("Failed to start paper trading. Exiting.", "ERROR")
        sys.exit(1)
    
    # Wait a moment for paper trading to initialize
    time.sleep(2)
    
    # Check if process is still running
    if paper_trade_process.poll() is not None:
        log("Paper trading process exited immediately. Check for errors.", "ERROR")
        sys.exit(1)
    
    log("Paper trading started successfully")
    
    # 2. Start calibration drift monitoring thread
    log("Starting calibration drift monitoring thread...")
    drift_thread = threading.Thread(
        target=periodic_task,
        args=(DRIFT_MONITOR_CMD, "Calibration drift monitor", DRIFT_CHECK_INTERVAL, 60),
        daemon=True,
        name="DriftMonitor"
    )
    drift_thread.start()
    log("Drift monitoring thread started")
    
    # 3. Start system integrity verification thread
    log("Starting system integrity verification thread...")
    integrity_thread = threading.Thread(
        target=periodic_task,
        args=(INTEGRITY_CHECK_CMD, "System integrity check", INTEGRITY_CHECK_INTERVAL, 120),
        daemon=True,
        name="IntegrityChecker"
    )
    integrity_thread.start()
    log("Integrity check thread started")
    
    print()
    print("=" * 70)
    print("MONITORING ACTIVE")
    print("=" * 70)
    print("Paper trading: Running in background")
    print("Drift monitoring: Every 30 minutes")
    print("Integrity checks: Every 60 minutes")
    print("Log file: auto_monitor.log")
    print()
    print("Press Ctrl+C to stop all processes")
    print("=" * 70)
    print()
    
    log("All monitoring threads started. Waiting for paper trading to complete...")
    
    # Wait for paper trading process to finish
    try:
        while True:
            # Check if paper trading is still running
            if paper_trade_process.poll() is not None:
                return_code = paper_trade_process.returncode
                if return_code == 0:
                    log("Paper trading session completed successfully")
                else:
                    log(f"Paper trading session ended with code {return_code}", "WARNING")
                break
            
            # Check if monitoring threads are still alive
            if not drift_thread.is_alive():
                log("Drift monitoring thread died unexpectedly", "WARNING")
            
            if not integrity_thread.is_alive():
                log("Integrity check thread died unexpectedly", "WARNING")
            
            time.sleep(10)  # Check every 10 seconds
        
        log("=" * 70)
        log("Automated Paper Trading Monitor Completed")
        log("=" * 70)
        
        print()
        print("=" * 70)
        print("MONITORING COMPLETED")
        print("=" * 70)
        print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Log file: {LOG_FILE}")
        print("=" * 70)
        
    except KeyboardInterrupt:
        print()
        log("User interrupted. Terminating all processes...", "INFO")
        print("Stopping paper trading...")
        
        if paper_trade_process.poll() is None:
            paper_trade_process.terminate()
            try:
                paper_trade_process.wait(timeout=5)
                log("Paper trading process terminated")
            except subprocess.TimeoutExpired:
                log("Force killing paper trading process...", "WARNING")
                paper_trade_process.kill()
        
        log("=" * 70)
        log("Automated Paper Trading Monitor Stopped by User")
        log("=" * 70)
        
        print()
        print("=" * 70)
        print("MONITORING STOPPED")
        print("=" * 70)
        print(f"Stopped: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Log file: {LOG_FILE}")
        print("=" * 70)
        
        sys.exit(0)

if __name__ == "__main__":
    main()








