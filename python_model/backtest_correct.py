"""
Backtest with Correct Features - XAUUSD Daily
"""

import pandas as pd
import numpy as np
import pickle
from features import compute_indicators, get_feature_columns

print("=" * 70)
print("BACKTEST - XAUUSD DAILY (Correct Features)")
print("=" * 70)
print()

# Load data
df = pd.read_csv('gold_data.csv')
df['Date'] = pd.to_datetime(df['Date'])
df = df.sort_values('Date')
df = df[df['Date'] >= '2023-01-01'].reset_index(drop=True)
df = df.set_index(pd.to_datetime(df['Date']))

print(f"📊 Loaded {len(df)} candles ({df.index.min().date()} to {df.index.max().date()})")

# Compute features
print("Computing indicators...", end=" ")
df = compute_indicators(df)
print("✅")

# Get the EXACT features used by the model
feature_cols = get_feature_columns()
print(f"Using {len(feature_cols)} features: {feature_cols}")
print()

# Clean
df_clean = df.dropna(subset=feature_cols)
print(f"Complete rows: {len(df_clean)}")
print()

# Load model
model = pickle.load(open('xgb_1d.pkl', 'rb'))
calibrator = pickle.load(open('calibrator_1d.pkl', 'rb'))
print("✅ Model loaded")
print()

# === BACKTEST ===
print("Running backtest...")
print()

trades = []
capital = 10000
peak = capital
dd_max = 0
wins = losses = 0
signals = 0

for i in range(len(df_clean) - 5):
    row = df_clean.iloc[i]
    
    X = row[feature_cols].values.reshape(1, -1)
    
    try:
        # Predict
        prob = model.predict_proba(X)[0][1]
        calib_models = pickle.load(open('calibrator_1d.pkl', 'rb'))
        if isinstance(calib_models, dict):
            calibrator_1d = calib_models.get('1d', calib_models.get(list(calib_models.keys())[0]))
        else:
            calibrator_1d = calib_models
        prob_cal = calibrator_1d.predict([[prob]])[0]
        
        direction = "UP" if prob >= 0.5 else "DOWN"
        conf_raw = (prob if prob >= 0.5 else 1-prob) * 100
        conf_cal = (prob_cal if prob >= 0.5 else 1-prob_cal) * 100
        
        # Lower threshold for backtesting
        if conf_cal < 52:
            continue
        
        signals += 1
        
        # Position
        price = row['Close']
        atr = row['ATR']
        sl_dist = 2 * atr
        tp_dist = sl_dist * 2.5
        
        risk = capital * 0.0075
        lots = min(10, max(0.01, risk / (sl_dist * 100)))
        
        entry = price
        sl = price - sl_dist if direction == "UP" else price + sl_dist
        tp = price + tp_dist if direction == "UP" else price - tp_dist
        
        # Find exit
        result = None
        exit_price = None
        
        for j in range(i+1, min(i+6, len(df_clean))):
            h = df_clean.iloc[j]['High']
            l = df_clean.iloc[j]['Low']
            
            if direction == "UP":
                if h >= tp:
                    exit_price = tp
                    result = "WIN"
                    break
                elif l <= sl:
                    exit_price = sl
                    result = "LOSS"
                    break
            else:
                if l <= tp:
                    exit_price = tp
                    result = "WIN"
                    break
                elif h >= sl:
                    exit_price = sl
                    result = "LOSS"
                    break
        
        if result is None:
            exit_price = df_clean.iloc[min(i+5, len(df_clean)-1)]['Close']
            result = "WIN" if (direction == "UP" and exit_price > entry) or (direction == "DOWN" and exit_price < entry) else "LOSS"
        
        # P&L
        pnl = (risk * 2.5) if result == "WIN" else -risk
        capital += pnl
        peak = max(peak, capital)
        dd_max = max(dd_max, (peak - capital) / peak if peak > 0 else 0)
        
        if result == "WIN":
            wins += 1
        else:
            losses += 1
        
        trades.append({
            'date': row.name,
            'direction': direction,
            'entry': entry,
            'exit': exit_price,
            'result': result,
            'pnl': pnl,
            'capital': capital,
            'conf_raw': conf_raw,
            'conf_cal': conf_cal
        })
        
    except Exception as e:
        print(f"Error: {e}")
        continue

print("=" * 70)
print("BACKTEST RESULTS")
print("=" * 70)
print()

if len(trades) > 0:
    df_trades = pd.DataFrame(trades)
    total = len(df_trades)
    total_pnl = df_trades['pnl'].sum()
    wr = wins / total if total > 0 else 0
    gross_win = df_trades[df_trades['pnl'] > 0]['pnl'].sum()
    gross_loss = abs(df_trades[df_trades['pnl'] < 0]['pnl'].sum())
    pf = gross_win / gross_loss if gross_loss > 0 else 0
    
    print(f"💰 CAPITAL:")
    print(f"   Start: $10,000")
    print(f"   End: ${capital:,.0f}")
    print(f"   Profit: ${total_pnl:,.0f}")
    print(f"   ROI: {(total_pnl / 10000 * 100):.2f}%")
    print()
    
    print(f"📈 PERFORMANCE:")
    print(f"   Signals Generated: {signals}")
    print(f"   Trades Taken: {total}")
    print(f"   Wins: {wins} ({wr*100:.1f}%)")
    print(f"   Losses: {losses} ({(1-wr)*100:.1f}%)")
    print()
    
    print(f"📊 STATISTICS:")
    print(f"   Avg P&L/Trade: ${total_pnl/total:,.0f}")
    print(f"   Profit Factor: {pf:.2f}")
    print(f"   Max Drawdown: {dd_max*100:.2f}%")
    print(f"   Avg Confidence: {df_trades['conf_cal'].mean():.1f}%")
    print()
    
    # By direction
    ups = len(df_trades[df_trades['direction'] == 'UP'])
    ups_w = len(df_trades[(df_trades['direction'] == 'UP') & (df_trades['result'] == 'WIN')])
    downs = len(df_trades[df_trades['direction'] == 'DOWN'])
    downs_w = len(df_trades[(df_trades['direction'] == 'DOWN') & (df_trades['result'] == 'WIN')])
    
    print(f"📍 BY DIRECTION:")
    print(f"   UP: {ups} ({(ups_w/ups*100 if ups > 0 else 0):.1f}% win)")
    print(f"   DOWN: {downs} ({(downs_w/downs*100 if downs > 0 else 0):.1f}% win)")
    print()
    
    exp_val = (wr * (capital*0.0075*2.5)) - ((1-wr) * (capital*0.0075))
    print(f"Expected Value/Trade: ${exp_val:,.0f}")
    print()
    
    df_trades.to_csv('backtest_results.csv', index=False)
    print("✅ Results saved: backtest_results.csv")
else:
    print("❌ No trades generated")

print()
print("=" * 70)
