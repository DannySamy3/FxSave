"""
Data Manager Module - Incremental Data Fetching and Caching
Handles live data updates without overwriting historical data.

Features:
- Incremental candle fetching
- Local caching to disk
- Timeframe-specific data management
- Append-only updates (no overwrites)
- Data validation and integrity checks
"""

import pandas as pd
import numpy as np
import yfinance as yf
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
import threading
import time

# Lock for thread-safe file operations
_data_lock = threading.Lock()


class DataManager:
    """
    Manages market data fetching, caching, and incremental updates.
    Ensures data integrity and append-only updates.
    """
    
    def __init__(self, symbol='GC=F', cache_dir=None):
        """
        Args:
            symbol: Yahoo Finance symbol (GC=F for Gold Futures)
            cache_dir: Directory for data cache (default: ./cache)
        """
        self.symbol = symbol
        self.cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / 'cache'
        self.cache_dir.mkdir(exist_ok=True)
        
        # Timeframe configurations
        self.timeframe_config = {
            '15m': {
                'interval': '15m',
                'max_history_days': 59,  # Yahoo limit
                'resample': None
            },
            '30m': {
                'interval': '30m',
                'max_history_days': 59,
                'resample': None
            },
            '1h': {
                'interval': '1h',
                'max_history_days': 729,
                'resample': None
            },
            '4h': {
                'interval': '1h',  # Fetch 1h, resample to 4h
                'max_history_days': 729,
                'resample': '4h'
            },
            '1d': {
                'interval': '1d',
                'max_history_days': 3650,  # ~10 years
                'resample': None
            }
        }
        
        # Track last update times
        self._last_update = {}
        self._load_metadata()
    
    def _get_cache_path(self, timeframe):
        """Get cache file path for a timeframe"""
        return self.cache_dir / f'{self.symbol.replace("=", "_")}_{timeframe}.csv'
    
    def _get_metadata_path(self):
        """Get metadata file path"""
        return self.cache_dir / 'metadata.json'
    
    def _load_metadata(self):
        """Load metadata from disk"""
        meta_path = self._get_metadata_path()
        if meta_path.exists():
            try:
                with open(meta_path, 'r') as f:
                    meta = json.load(f)
                    self._last_update = {k: datetime.fromisoformat(v) for k, v in meta.get('last_update', {}).items()}
            except:
                self._last_update = {}
        else:
            self._last_update = {}
    
    def _save_metadata(self):
        """Save metadata to disk"""
        meta_path = self._get_metadata_path()
        meta = {
            'last_update': {k: v.isoformat() for k, v in self._last_update.items()},
            'symbol': self.symbol,
            'updated_at': datetime.now().isoformat()
        }
        with open(meta_path, 'w') as f:
            json.dump(meta, f, indent=2)
    
    def get_cached_data(self, timeframe):
        """
        Load cached data for a timeframe.
        Returns DataFrame or None if no cache.
        """
        cache_path = self._get_cache_path(timeframe)
        
        if not cache_path.exists():
            return None
        
        try:
            df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
            df.index = pd.to_datetime(df.index)
            return df
        except Exception as e:
            print(f"  ⚠️ Error reading cache for {timeframe}: {e}")
            return None
    
    def _fetch_from_yahoo(self, timeframe, start_date=None, end_date=None):
        """
        Fetch data from Yahoo Finance.
        """
        config = self.timeframe_config[timeframe]
        interval = config['interval']
        
        # Calculate period/dates
        if start_date:
            df = yf.download(
                self.symbol,
                start=start_date,
                end=end_date or datetime.now(),
                interval=interval,
                progress=False
            )
        else:
            # Use period for initial fetch
            max_days = config['max_history_days']
            df = yf.download(
                self.symbol,
                period=f'{max_days}d',
                interval=interval,
                progress=False
            )
        
        if df.empty:
            return pd.DataFrame()
        
        # Handle MultiIndex columns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        # Resample if needed (e.g., 1h → 4h)
        if config['resample']:
            resample_logic = {
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum'
            }
            resample_logic = {k: v for k, v in resample_logic.items() if k in df.columns}
            df = df.resample(config['resample']).agg(resample_logic).dropna()
        
        return df
    
    def fetch_initial_data(self, timeframe, force=False):
        """
        Fetch initial/full historical data for a timeframe.
        Only fetches if no cache exists or force=True.
        """
        cache_path = self._get_cache_path(timeframe)
        
        if cache_path.exists() and not force:
            print(f"  ✓ Using cached data for {timeframe}")
            return self.get_cached_data(timeframe)
        
        print(f"  📥 Fetching full history for {timeframe}...")
        df = self._fetch_from_yahoo(timeframe)
        
        if df.empty:
            print(f"  ⚠️ No data received for {timeframe}")
            return pd.DataFrame()
        
        # Save to cache
        with _data_lock:
            df.to_csv(cache_path)
            self._last_update[timeframe] = datetime.now()
            self._save_metadata()
        
        print(f"  ✓ Cached {len(df)} rows for {timeframe}")
        return df
    
    def fetch_incremental_update(self, timeframe):
        """
        Fetch only new candles since last update (append-only).
        Returns tuple: (full_df, new_rows_count)
        """
        cached = self.get_cached_data(timeframe)
        
        if cached is None or cached.empty:
            # No cache, do full fetch
            df = self.fetch_initial_data(timeframe)
            return df, len(df)
        
        # Get last candle timestamp
        last_timestamp = cached.index[-1]
        
        # Fetch new data starting from last timestamp
        # Add buffer to ensure overlap
        start_date = last_timestamp - timedelta(hours=4)
        
        print(f"  📡 Fetching updates for {timeframe} since {last_timestamp}...")
        new_data = self._fetch_from_yahoo(timeframe, start_date=start_date)
        
        if new_data.empty:
            print(f"  ⚠️ No new data for {timeframe}")
            return cached, 0
        
        # Filter to only truly new rows
        new_rows = new_data[new_data.index > last_timestamp]
        
        if new_rows.empty:
            print(f"  ✓ {timeframe} is up to date")
            return cached, 0
        
        # Append new rows (append-only, no overwrites)
        with _data_lock:
            combined = pd.concat([cached, new_rows])
            combined = combined[~combined.index.duplicated(keep='last')]
            combined = combined.sort_index()
            
            # Save to cache
            cache_path = self._get_cache_path(timeframe)
            combined.to_csv(cache_path)
            
            self._last_update[timeframe] = datetime.now()
            self._save_metadata()
        
        print(f"  ✓ Added {len(new_rows)} new rows to {timeframe}")
        return combined, len(new_rows)
    
    def get_latest_candle(self, timeframe):
        """
        Get the most recent complete candle for a timeframe.
        """
        df = self.get_cached_data(timeframe)
        
        if df is None or df.empty:
            return None
        
        return df.iloc[-1].to_dict()
    
    def get_data_for_prediction(self, timeframe, lookback=500):
        """
        Get data ready for prediction with sufficient lookback.
        Returns DataFrame with at least `lookback` rows.
        
        Note: Increased default lookback to 500 to ensure enough rows remain
        after indicator computation and dropna() operations.
        EMA_200 needs 200 rows, TSI needs ~25 rows, so we need extra buffer.
        """
        df = self.get_cached_data(timeframe)
        
        if df is None or df.empty:
            # Try to fetch
            df = self.fetch_initial_data(timeframe)
        
        if df is None or len(df) < lookback:
            # If we don't have enough, return what we have (but warn)
            if df is not None and len(df) >= 50:
                print(f"  ⚠️ Limited data for {timeframe}: {len(df)} rows (requested {lookback})")
                return df.copy()
            else:
                print(f"  ⚠️ Insufficient data for {timeframe}: {len(df) if df is not None else 0} < {lookback}")
                return None
        
        # Return last `lookback` rows for feature computation
        return df.tail(lookback).copy()
    
    def update_all_timeframes(self):
        """
        Update all timeframes with new data.
        Returns dict of {timeframe: new_rows_count}
        """
        results = {}
        
        for tf in self.timeframe_config.keys():
            try:
                _, new_count = self.fetch_incremental_update(tf)
                results[tf] = new_count
            except Exception as e:
                print(f"  ❌ Error updating {tf}: {e}")
                results[tf] = -1
        
        return results
    
    def get_update_status(self):
        """
        Get status of data updates for all timeframes.
        """
        status = {}
        
        for tf in self.timeframe_config.keys():
            cache_path = self._get_cache_path(tf)
            cached = self.get_cached_data(tf)
            
            status[tf] = {
                'has_cache': cache_path.exists(),
                'rows': len(cached) if cached is not None else 0,
                'last_update': self._last_update.get(tf, None),
                'last_candle': cached.index[-1].isoformat() if cached is not None and not cached.empty else None
            }
        
        return status
    
    def needs_update(self, timeframe):
        """
        Check if a timeframe needs an update based on candle completion time.
        """
        last_update = self._last_update.get(timeframe)
        
        if last_update is None:
            return True
        
        # Determine expected update interval
        intervals = {
            '15m': timedelta(minutes=15),
            '30m': timedelta(minutes=30),
            '1h': timedelta(hours=1),
            '4h': timedelta(hours=4),
            '1d': timedelta(days=1)
        }
        
        interval = intervals.get(timeframe, timedelta(hours=1))
        
        # Add small buffer
        return datetime.now() - last_update > interval
    
    def cleanup_old_cache(self, keep_days=30):
        """
        Remove cache files older than specified days.
        """
        cutoff = datetime.now() - timedelta(days=keep_days)
        
        for file in self.cache_dir.glob('*.csv'):
            if file.stat().st_mtime < cutoff.timestamp():
                file.unlink()
                print(f"  🗑️ Removed old cache: {file.name}")


# Singleton instance for easy access
_data_manager_instance = None

def get_data_manager(symbol='GC=F'):
    """Get or create singleton DataManager instance"""
    global _data_manager_instance
    if _data_manager_instance is None:
        _data_manager_instance = DataManager(symbol)
    return _data_manager_instance


if __name__ == "__main__":
    # Test data manager
    dm = DataManager()
    
    print("=" * 50)
    print("Data Manager Test")
    print("=" * 50)
    
    # Update all timeframes
    results = dm.update_all_timeframes()
    
    print("\nUpdate Results:")
    for tf, count in results.items():
        print(f"  {tf}: {count} new rows")
    
    print("\nStatus:")
    status = dm.get_update_status()
    for tf, info in status.items():
        print(f"  {tf}: {info['rows']} rows, last candle: {info['last_candle']}")

