"""
Fetch Multi-Timeframe XAUUSD Data and Run Backtest
Downloads fresh data from yfinance for all timeframes
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pickle

print("=" * 70)
print("FETCHING MULTI-TIMEFRAME XAUUSD DATA")
print("=" * 70)

# Fetch data for last 12 months
end_date = datetime.now()
start_date = end_date - timedelta(days=365)

print(f"Date range: {start_date.date()} to {end_date.date()}")
print()

timeframes = {
    '1d': '1d',
    '4h': '4h',
    '1h': '1h',
    '30m': '30m',
    '15m': '15m'
}

data_dict = {}

for tf_name, interval in timeframes.items():
    print(f"Fetching {tf_name}...", end=" ")
    try:
        df = yf.download('GC=F', start=start_date, end=end_date, interval=interval, progress=False)
        df = df.reset_index()
        df.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
        df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]
        data_dict[tf_name] = df
        print(f"✅ {len(df)} candles")
    except Exception as e:
        print(f"❌ Error: {e}")

print()
print("=" * 70)
print("BACKTEST SETUP")
print("=" * 70)
print()

# Use 1d data for backtest (most reliable)
df_1d = data_dict['1d']

print(f"Using 1d timeframe: {len(df_1d)} candles")
print(f"Date range: {df_1d['Date'].min()} to {df_1d['Date'].max()}")
print()

# Load trained model
try:
    model = pickle.load(open('xgb_1d.pkl', 'rb'))
    calibrator = pickle.load(open('calibrator_1d.pkl', 'rb'))
    print("✅ Model and calibrator loaded")
except Exception as e:
    print(f"❌ Error loading model: {e}")
    exit(1)

# Compute features needed by model
from features import compute_indicators

print("Computing technical indicators...", end=" ")
df_1d = compute_indicators(df_1d.copy())
print("✅")
print()

# Feature columns
feature_cols = [
    'Close', 'High', 'Low', 'Open', 'Volume',
    'EMA_10', 'EMA_50', 'RSI', 'ATR',
    'MACD', 'MACD_Signal', 'MACD_Hist',
    'Price_to_EMA10', 'Price_to_EMA50'
]

# Clean data
df_clean = df_1d.dropna(subset=feature_cols).copy()
print(f"Rows with complete features: {len(df_clean)}")
print()

# === BACKTEST ===
print("=" * 70)
print("RUNNING BACKTEST")
print("=" * 70)
print()

trades_log = []
capital = 10000
initial_capital = 10000
peak_capital = capital
max_drawdown = 0
wins = 0
losses = 0
no_trades = 0

for idx in range(len(df_clean) - 5):  # Leave last 5 for exit simulation
    row = df_clean.iloc[idx]
    date = row['Date']
    
    # Extract features
    X = row[feature_cols].values.reshape(1, -1)
    
    try:
        # Raw prediction
        raw_pred_proba = model.predict_proba(X)[0]
        raw_prob_up = raw_pred_proba[1]
        pred_class = model.predict(X)[0]
        
        # Calibrate
        calib_prob_up = calibrator.predict([[raw_prob_up]])[0]
        
        # Direction
        if raw_prob_up >= 0.5:
            direction = "UP"
            raw_conf = raw_prob_up * 100
            calib_conf = calib_prob_up * 100
        else:
            direction = "DOWN"
            raw_conf = (1 - raw_prob_up) * 100
            calib_conf = (1 - calib_prob_up) * 100
        
        # Filter: min 60% confidence
        if calib_conf < 60:
            no_trades += 1
            continue
        
        # Position sizing
        current_price = row['Close']
        atr = row['ATR']
        
        sl_distance = 2 * atr
        tp_distance = sl_distance * 2.5
        
        risk_pct = 0.0075
        risk_amount = capital * risk_pct
        lots = min(10.0, max(0.01, risk_amount / (sl_distance * 100)))
        
        # Setup trade
        if direction == "UP":
            entry = current_price
            sl = current_price - sl_distance
            tp = current_price + tp_distance
        else:
            entry = current_price
            sl = current_price + sl_distance
            tp = current_price - tp_distance
        
        # Find exit
        result = None
        exit_price = None
        exit_idx = None
        
        for j in range(idx + 1, min(idx + 6, len(df_clean))):
            future_high = df_clean.iloc[j]['High']
            future_low = df_clean.iloc[j]['Low']
            
            if direction == "UP":
                if future_high >= tp:
                    exit_price = tp
                    result = "win"
                    exit_idx = j
                    break
                elif future_low <= sl:
                    exit_price = sl
                    result = "loss"
                    exit_idx = j
                    break
            else:
                if future_low <= tp:
                    exit_price = tp
                    result = "win"
                    exit_idx = j
                    break
                elif future_high >= sl:
                    exit_price = sl
                    result = "loss"
                    exit_idx = j
                    break
        
        if result is None:
            exit_idx = min(idx + 5, len(df_clean) - 1)
            exit_price = df_clean.iloc[exit_idx]['Close']
            result = "win" if (direction == "UP" and exit_price >= entry) or (direction == "DOWN" and exit_price <= entry) else "loss"
        
        # P&L
        if result == "win":
            pnl = risk_amount * 2.5
            wins += 1
        else:
            pnl = -risk_amount
            losses += 1
        
        capital += pnl
        peak_capital = max(peak_capital, capital)
        max_drawdown = max(max_drawdown, (peak_capital - capital) / peak_capital)
        
        trades_log.append({
            'date': date,
            'direction': direction,
            'entry': entry,
            'exit': exit_price,
            'sl': sl,
            'tp': tp,
            'result': result,
            'pnl': pnl,
            'capital': capital,
            'raw_conf': raw_conf,
            'calib_conf': calib_conf
        })
        
    except Exception as e:
        continue

# === RESULTS ===
print("=" * 70)
print("BACKTEST RESULTS - XAUUSD DAILY")
print("=" * 70)
print()

if len(trades_log) > 0:
    trades_df = pd.DataFrame(trades_log)
    
    total_trades = len(trades_df)
    win_rate = wins / total_trades if total_trades > 0 else 0
    total_pnl = trades_df['pnl'].sum()
    gross_profit = trades_df[trades_df['pnl'] > 0]['pnl'].sum()
    gross_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
    
    print(f"💰 CAPITAL PERFORMANCE:")
    print(f"   Initial: ${initial_capital:,.0f}")
    print(f"   Final: ${capital:,.0f}")
    print(f"   Profit/Loss: ${total_pnl:,.0f}")
    print(f"   ROI: {(total_pnl / initial_capital * 100):.2f}%")
    print()
    
    print(f"📊 TRADE STATISTICS:")
    print(f"   Total Trades: {total_trades}")
    print(f"   Wins: {wins} ({win_rate*100:.1f}%)")
    print(f"   Losses: {losses} ({(1-win_rate)*100:.1f}%)")
    print(f"   Avg Win/Loss: ${total_pnl / total_trades:,.0f}")
    print(f"   Profit Factor: {profit_factor:.2f}")
    print(f"   Signals Blocked (Low Conf): {no_trades}")
    print()
    
    print(f"⚠️ RISK METRICS:")
    print(f"   Max Drawdown: {max_drawdown*100:.2f}%")
    print(f"   Avg Trade Size: {trades_df['pnl'].abs().mean():,.0f}")
    print()
    
    print(f"📈 TRADE CHARACTERISTICS:")
    print(f"   Avg Raw Confidence: {trades_df['raw_conf'].mean():.1f}%")
    print(f"   Avg Calibrated Confidence: {trades_df['calib_conf'].mean():.1f}%")
    print(f"   Avg Pips per Trade: {abs(trades_df['exit'] - trades_df['entry']).mean():.2f}")
    print()
    
    # Direction analysis
    ups = len(trades_df[trades_df['direction'] == 'UP'])
    downs = len(trades_df[trades_df['direction'] == 'DOWN'])
    up_wr = (len(trades_df[(trades_df['direction'] == 'UP') & (trades_df['result'] == 'win')]) / ups * 100) if ups > 0 else 0
    down_wr = (len(trades_df[(trades_df['direction'] == 'DOWN') & (trades_df['result'] == 'win')]) / downs * 100) if downs > 0 else 0
    
    print(f"📍 DIRECTION BREAKDOWN:")
    print(f"   UP trades: {ups} ({up_wr:.1f}% win rate)")
    print(f"   DOWN trades: {downs} ({down_wr:.1f}% win rate)")
    print()
    
    # Save
    trades_df.to_csv('backtest_multi_tf_results.csv', index=False)
    print("✅ Results saved to backtest_multi_tf_results.csv")
    
else:
    print("❌ No trades executed during backtest")

print()
print("=" * 70)
