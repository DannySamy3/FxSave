"""
Update Logger Module
Logs CSV updates and model learning events with timestamps.

Features:
- JSON-based logging
- Timestamp tracking
- Success/failure status
- Audit trail for all updates
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class UpdateLogger:
    """
    Logger for CSV updates and model learning events.
    """
    
    def __init__(self, log_dir=None):
        """
        Initialize logger.
        
        Args:
            log_dir: Directory for log files (default: ./logs)
        """
        self.base_dir = Path(__file__).parent
        self.log_dir = Path(log_dir) if log_dir else self.base_dir / 'logs'
        self.log_dir.mkdir(exist_ok=True)
        
        # Log file paths
        self.csv_log_path = self.log_dir / 'csv_update_log.json'
        self.model_log_path = self.log_dir / 'model_learning_log.json'
        
        # Initialize log files if they don't exist
        self._init_log_file(self.csv_log_path)
        self._init_log_file(self.model_log_path)
    
    def _init_log_file(self, log_path: Path):
        """Initialize log file with empty list if it doesn't exist"""
        if not log_path.exists():
            with open(log_path, 'w') as f:
                json.dump([], f, indent=2)
    
    def _read_log(self, log_path: Path) -> List[Dict]:
        """Read log file and return list of entries"""
        try:
            with open(log_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def _write_log(self, log_path: Path, entries: List[Dict]):
        """Write log entries to file"""
        with open(log_path, 'w') as f:
            json.dump(entries, f, indent=2, default=str)
    
    def log_update(self, result: Dict):
        """
        Log an update operation (CSV or model learning).
        
        Args:
            result: Dict with operation details including:
                - timestamp: ISO format timestamp
                - operation: 'csv_update' or 'model_learning'
                - status: 'success', 'failed', 'skipped'
                - error: Error message if failed
                - Other operation-specific fields
        """
        operation = result.get('operation', 'unknown')
        
        if operation == 'csv_update':
            log_path = self.csv_log_path
        elif operation == 'model_learning':
            log_path = self.model_log_path
        else:
            # Unknown operation - log to both or create generic log
            log_path = self.log_dir / 'update_log.json'
            self._init_log_file(log_path)
        
        # Read existing entries
        entries = self._read_log(log_path)
        
        # Add new entry
        entries.append(result)
        
        # Keep only last 1000 entries (prevent log file from growing too large)
        if len(entries) > 1000:
            entries = entries[-1000:]
        
        # Write back
        self._write_log(log_path, entries)
    
    def get_last_update(self, operation: str) -> Optional[Dict]:
        """
        Get the last update entry for an operation.
        
        Args:
            operation: 'csv_update' or 'model_learning'
            
        Returns:
            Last update entry dict or None
        """
        if operation == 'csv_update':
            log_path = self.csv_log_path
        elif operation == 'model_learning':
            log_path = self.model_log_path
        else:
            return None
        
        entries = self._read_log(log_path)
        if entries:
            return entries[-1]
        return None
    
    def get_update_history(self, operation: str, limit: int = 100) -> List[Dict]:
        """
        Get update history for an operation.
        
        Args:
            operation: 'csv_update' or 'model_learning'
            limit: Maximum number of entries to return
            
        Returns:
            List of update entries (most recent first)
        """
        if operation == 'csv_update':
            log_path = self.csv_log_path
        elif operation == 'model_learning':
            log_path = self.model_log_path
        else:
            return []
        
        entries = self._read_log(log_path)
        return entries[-limit:][::-1]  # Most recent first
    
    def get_failed_updates(self, operation: str, days: int = 7) -> List[Dict]:
        """
        Get failed updates in the last N days.
        
        Args:
            operation: 'csv_update' or 'model_learning'
            days: Number of days to look back
            
        Returns:
            List of failed update entries
        """
        from datetime import timedelta
        
        cutoff = datetime.now() - timedelta(days=days)
        history = self.get_update_history(operation, limit=1000)
        
        failed = []
        for entry in history:
            if entry.get('status') == 'failed':
                entry_time = datetime.fromisoformat(entry['timestamp'])
                if entry_time >= cutoff:
                    failed.append(entry)
        
        return failed
    
    def get_statistics(self, operation: str, days: int = 30) -> Dict:
        """
        Get statistics for an operation over the last N days.
        
        Args:
            operation: 'csv_update' or 'model_learning'
            days: Number of days to analyze
            
        Returns:
            Dict with statistics
        """
        from datetime import timedelta
        
        cutoff = datetime.now() - timedelta(days=days)
        history = self.get_update_history(operation, limit=1000)
        
        stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'last_success': None,
            'last_failure': None,
            'consecutive_failures': 0
        }
        
        for entry in history:
            entry_time = datetime.fromisoformat(entry['timestamp'])
            if entry_time < cutoff:
                continue
            
            stats['total'] += 1
            status = entry.get('status', 'unknown')
            
            if status == 'success':
                stats['success'] += 1
                if stats['last_success'] is None:
                    stats['last_success'] = entry['timestamp']
            elif status == 'failed':
                stats['failed'] += 1
                if stats['last_failure'] is None:
                    stats['last_failure'] = entry['timestamp']
            elif status == 'skipped':
                stats['skipped'] += 1
        
        # Calculate consecutive failures (from most recent)
        for entry in history:
            if entry.get('status') == 'failed':
                stats['consecutive_failures'] += 1
            else:
                break
        
        return stats

