import pandas as pd
from datetime import datetime
from collections import defaultdict

# Read CSV with more error tolerance
try:
    df = pd.read_csv('forward_test_log.csv', on_bad_lines='skip')
except:
    # Alternative: manually parse
    with open('forward_test_log.csv') as f:
        lines = f.readlines()
    
    data = []
    for line in lines[1:]:  # Skip header
        parts = line.strip().split(',')
        if len(parts) >= 12:
            try:
                data.append({
                    'timestamp': parts[0],
                    'symbol': parts[1],
                    'timeframe': parts[2],
                    'direction': parts[3],
                    'decision': parts[10]
                })
            except:
                pass
    
    df = pd.DataFrame(data)

# Count by decision
if len(df) > 0:
    print("=" * 60)
    print("TRADE FREQUENCY ANALYSIS")
    print("=" * 60)
    
    trades = df[df['decision'].str.contains('TRADE', na=False)]
    no_trades = df[df['decision'].str.contains('NO_TRADE', na=False)]
    
    print(f"\nTotal Signals: {len(df):,}")
    print(f"TRADE Signals: {len(trades):,} ({len(trades)/len(df)*100:.1f}%)")
    print(f"NO_TRADE Signals: {len(no_trades):,} ({len(no_trades)/len(df)*100:.1f}%)")
    
    # Extract date and count
    df['date'] = df['timestamp'].str[:10]
    
    trades_by_date = trades.groupby('date').size()
    trades_by_timeframe = trades.groupby('timeframe').size()
    
    print(f"\nTRADES BY DATE:")
    total_trading_dates = 0
    total_trades = 0
    for date in sorted(trades_by_date.index):
        count = trades_by_date[date]
        print(f"  {date}: {count} trades")
        total_trades += count
        total_trading_dates += 1
    
    print(f"\nTRADES BY TIMEFRAME:")
    for tf in sorted(trades_by_timeframe.index):
        count = trades_by_timeframe[tf]
        print(f"  {tf}: {count} trades ({count/len(trades)*100:.1f}%)")
    
    if total_trading_dates > 0:
        avg_per_day = total_trades / total_trading_dates
        weekly_estimate = avg_per_day * 5
        print(f"\n💡 WEEKLY FORECAST:")
        print(f"  Avg trades/day: {avg_per_day:.1f}")
        print(f"  Estimated per week: ~{weekly_estimate:.0f} trades (5 trading days)")
        print(f"  Per month estimate: ~{weekly_estimate * 4:.0f} trades")
    
    # Rejection analysis
    print(f"\nREJECTION ANALYSIS:")
    rejection_reasons = no_trades['decision'].value_counts()
    for reason, count in rejection_reasons.head(5).items():
        print(f"  {reason}: {count}")
