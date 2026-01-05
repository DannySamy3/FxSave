"""
Forward Testing / Paper Trading Module (HARDENED v2.0)
Logs every prediction to a persistent CSV.
Tracks "What actually happened" vs "What we predicted".

FIXES APPLIED:
- Added 'lots' field to CSV
- Added all required fields for audit
- Added HTF status tracking
- Improved error handling
- Added summary statistics
"""
import pandas as pd
import os
import csv
from datetime import datetime


# Complete field list for audit requirements (23 columns for forward test schema)
CSV_COLUMNS = [
    'timestamp',
    'symbol',
    'timeframe',
    'direction',
    'raw_conf',
    'calib_conf',
    'calib_drift',
    'regime',
    'htf_status',
    'htf_parent',
    'decision',
    'reason',
    'entry',
    'sl',
    'tp',
    'lots',
    'risk_pct',
    'risk_amount',
    'rr_ratio',
    'close_price_at_pred',
    # News fields (enhanced for v2.2.0)
    'news_sentiment',
    'news_high_impact',
    'news_headlines',
    'news_event',
    'news_impact_level',
    'news_cooldown_minutes',
    'news_block_until'
]


class ForwardTester:
    """
    Forward testing logger for tracking predictions and decisions.
    Logs all TRADE and NO_TRADE decisions with full context.
    """
    
    def __init__(self, log_path="forward_test_log.csv"):
        self.log_path = log_path
        self._init_log()
        
    def _init_log(self):
        """Create CSV with header if file doesn't exist"""
        if not os.path.exists(self.log_path):
            try:
                with open(self.log_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(CSV_COLUMNS)
                print(f"  [OK] Created forward test log: {self.log_path}")
            except Exception as e:
                print(f"  [ERROR] Failed to create log file: {e}")
        else:
            # Verify columns match
            self._verify_columns()
    
    def _verify_columns(self):
        """Verify existing log has correct columns, migrate if needed"""
        try:
            with open(self.log_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                existing_columns = next(reader, None)
            
            if existing_columns != CSV_COLUMNS:
                print(f"  [!] Log columns mismatch, backup and recreate recommended")
                # Don't auto-migrate to preserve data
        except Exception as e:
            print(f"  [!] Could not verify log columns: {e}")
                
    def log_signal(self, timeframe, signal_data):
        """
        Append signal to log with all required fields.
        
        Args:
            timeframe: Timeframe string
            signal_data: Dict containing signal details
        """
        try:
            row = [
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                signal_data.get('symbol', 'XAUUSD'),
                timeframe,
                signal_data.get('direction', ''),
                round(signal_data.get('raw_confidence', 0), 4),
                round(signal_data.get('calibrated_confidence', 0), 4),
                round(signal_data.get('calibration_drift', 0), 4),
                signal_data.get('regime', 'UNKNOWN'),
                signal_data.get('htf_status', ''),
                signal_data.get('htf_parent', ''),
                signal_data.get('decision', 'NO_TRADE'),
                signal_data.get('reason', ''),
                signal_data.get('entry', 0),
                signal_data.get('sl', 0),
                signal_data.get('tp', 0),
                signal_data.get('lots', 0),
                signal_data.get('risk_pct', 0),
                signal_data.get('risk_amount', 0),
                signal_data.get('rr_ratio', 0),
                signal_data.get('current_price', 0),
                # News fields (enhanced for v2.2.0)
                round(signal_data.get('news_sentiment', 0), 3),
                signal_data.get('news_high_impact', False),
                signal_data.get('news_headlines', '')[:200],  # Truncate headlines
                signal_data.get('news_event', ''),
                signal_data.get('news_impact_level', ''),
                signal_data.get('news_cooldown_minutes', ''),
                signal_data.get('news_block_until', ''),
                # True recency validation fields
                signal_data.get('news_classification', ''),
                signal_data.get('news_origin_timestamp', ''),
                signal_data.get('news_fetch_timestamp', ''),
                signal_data.get('cache_age_minutes', '')
            ]
            
            with open(self.log_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(row)
                
        except Exception as e:
            print(f"  [ERROR] Failed to log signal: {e}")
            
    def compute_metrics(self, lookback_days=7):
        """
        Analyze the log file to calculate statistics.
        
        Args:
            lookback_days: Number of days to analyze
            
        Returns:
            Dict with metrics
        """
        if not os.path.exists(self.log_path):
            return {'error': 'Log file not found'}
            
        try:
            df = pd.read_csv(self.log_path, encoding='utf-8')
            
            if df.empty:
                return {'total_signals': 0}
            
            # Parse timestamps
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Filter to lookback period
            cutoff = datetime.now() - pd.Timedelta(days=lookback_days)
            df_recent = df[df['timestamp'] >= cutoff]
            
            # Basic counts
            total_signals = len(df_recent)
            trades_taken = len(df_recent[df_recent['decision'] == 'TRADE'])
            no_trades = total_signals - trades_taken
            
            # Rejection reasons breakdown
            rejections = df_recent[df_recent['decision'] == 'NO_TRADE']
            rejection_counts = rejections['reason'].value_counts().to_dict()
            
            # Per-timeframe breakdown
            tf_breakdown = df_recent.groupby(['timeframe', 'decision']).size().unstack(fill_value=0).to_dict('index')
            
            # HTF conflict rate
            htf_conflicts = len(df_recent[df_recent['htf_status'] == 'HARD_CONFLICT'])
            
            # Confidence stats
            conf_stats = {
                'mean_calib_conf': df_recent['calib_conf'].mean(),
                'mean_raw_conf': df_recent['raw_conf'].mean(),
                'mean_drift': df_recent['calib_drift'].mean()
            }
            
            return {
                'period_days': lookback_days,
                'total_signals': total_signals,
                'trades_taken': trades_taken,
                'no_trades': no_trades,
                'trade_rate': trades_taken / total_signals if total_signals > 0 else 0,
                'rejection_reasons': rejection_counts,
                'htf_conflicts': htf_conflicts,
                'by_timeframe': tf_breakdown,
                'confidence_stats': conf_stats,
                'last_signal': df_recent.iloc[-1]['timestamp'].isoformat() if not df_recent.empty else None
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def get_recent_signals(self, n=20):
        """Get the most recent N signals"""
        if not os.path.exists(self.log_path):
            return []
            
        try:
            df = pd.read_csv(self.log_path, encoding='utf-8')
            return df.tail(n).to_dict('records')
        except:
            return []
    
    def get_no_trade_analysis(self, lookback_days=30):
        """
        Analyze NO_TRADE decisions for audit purposes.
        Shows what percentage of signals are blocked and why.
        """
        if not os.path.exists(self.log_path):
            return {'error': 'Log file not found'}
            
        try:
            df = pd.read_csv(self.log_path, encoding='utf-8')
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            cutoff = datetime.now() - pd.Timedelta(days=lookback_days)
            df_recent = df[df['timestamp'] >= cutoff]
            
            no_trades = df_recent[df_recent['decision'] == 'NO_TRADE']
            
            analysis = {
                'total_signals': len(df_recent),
                'no_trade_count': len(no_trades),
                'no_trade_rate': len(no_trades) / len(df_recent) if len(df_recent) > 0 else 0,
                'by_reason': no_trades['reason'].value_counts().to_dict(),
                'by_timeframe': no_trades.groupby('timeframe')['reason'].value_counts().to_dict(),
                'by_regime': no_trades.groupby('regime')['reason'].value_counts().to_dict()
            }
            
            return analysis
            
        except Exception as e:
            return {'error': str(e)}
    
    def export_summary(self, output_path=None):
        """Export a summary report for audit"""
        metrics = self.compute_metrics(lookback_days=30)
        no_trade = self.get_no_trade_analysis(lookback_days=30)
        
        summary = {
            'generated_at': datetime.now().isoformat(),
            'period_metrics': metrics,
            'no_trade_analysis': no_trade
        }
        
        if output_path:
            import json
            with open(output_path, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
        
        return summary
