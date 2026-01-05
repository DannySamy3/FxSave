import pandas as pd

# Load forward test log
df = pd.read_csv('forward_test_log.csv')

# Basic stats
total_signals = len(df)
trades = len(df[df['decision'] == 'TRADE'])
no_trades = len(df[df['decision'] == 'NO_TRADE'])
trade_pct = (trades / total_signals * 100) if total_signals > 0 else 0

print("=" * 50)
print("FORWARD TEST STATISTICS")
print("=" * 50)
print(f"Total Signals Generated: {total_signals:,}")
print(f"TRADE Decisions: {trades} ({trade_pct:.1f}%)")
print(f"NO_TRADE Decisions: {no_trades} ({100-trade_pct:.1f}%)")
print()

# Rejection reasons breakdown
print("TOP REJECTION REASONS:")
rejection_reasons = df[df['decision'] == 'NO_TRADE']['reason'].value_counts()
for reason, count in rejection_reasons.head(10).items():
    pct = (count / no_trades * 100)
    print(f"  {reason}: {count} ({pct:.1f}%)")
print()

# Time analysis
df['timestamp'] = pd.to_datetime(df['timestamp'])
date_groups = df[df['decision'] == 'TRADE'].groupby(df['timestamp'].dt.date).size()

print("ACTUAL TRADES BY DATE:")
for date, count in date_groups.items():
    print(f"  {date}: {count} trades")
print()

# Weekly estimate
if len(date_groups) > 0:
    avg_trades_per_day = date_groups.mean()
    estimated_weekly = avg_trades_per_day * 5  # 5 trading days
    print(f"Average Trades/Day: {avg_trades_per_day:.1f}")
    print(f"Estimated Weekly: {estimated_weekly:.0f} trades (5 trading days)")
