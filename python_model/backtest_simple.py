"""
Simple Backtest Engine - Daily Timeframe Only
Tests model predictions against real XAUUSD daily data
"""

import pandas as pd
import numpy as np
import xgboost as xgb
from pathlib import Path
from datetime import datetime
import pickle

# Load data
df = pd.read_csv('gold_data.csv')
df['Date'] = pd.to_datetime(df['Date'])
df = df.sort_values('Date')

# Filter to recent data (2023 onwards)
df = df[df['Date'] >= '2023-01-01'].reset_index(drop=True)

print("=" * 70)
print("BACKTEST: XAUUSD Daily Predictions vs Historical Data")
print("=" * 70)
print(f"Data period: {df['Date'].min().date()} to {df['Date'].max().date()}")
print(f"Total candles: {len(df)}")
print()

# Load trained model
try:
    model = pickle.load(open('xgb_1d.pkl', 'rb'))
    calibrator = pickle.load(open('calibrator_1d.pkl', 'rb'))
    print("✅ Models loaded successfully")
except:
    print("❌ Error loading models")
    exit(1)

# Feature columns needed
feature_cols = [
    'Close', 'High', 'Low', 'Open', 'Volume',
    'EMA_10', 'EMA_50', 'RSI', 'ATR',
    'MACD', 'MACD_Signal', 'MACD_Hist',
    'Price_to_EMA10', 'Price_to_EMA50'
]

# Filter data with complete features
df_clean = df.dropna(subset=feature_cols).copy()
print(f"Complete feature rows: {len(df_clean)}")
print()

# === BACKTEST LOGIC ===
trades_log = []
capital = 10000
initial_capital = 10000
equity_curve = [{'date': df_clean.iloc[0]['Date'], 'capital': capital}]
peak_capital = capital
max_drawdown = 0
wins = 0
losses = 0
no_trades = 0

for idx in range(len(df_clean)):
    row = df_clean.iloc[idx]
    date = row['Date']
    
    # Extract features for prediction
    X = row[feature_cols].values.reshape(1, -1)
    
    try:
        # Raw prediction
        raw_pred_proba = model.predict_proba(X)[0]  # [prob_DOWN, prob_UP]
        raw_prob_up = raw_pred_proba[1]
        pred_class = model.predict(X)[0]  # 0=DOWN, 1=UP
        
        # Calibrate
        calib_prob_up = calibrator.predict([[raw_prob_up]])[0]
        
        # Determine direction and confidence
        if raw_prob_up >= 0.5:
            direction = "UP"
            raw_conf = raw_prob_up * 100
            calib_conf = calib_prob_up * 100
        else:
            direction = "DOWN"
            raw_conf = (1 - raw_prob_up) * 100
            calib_conf = (1 - calib_prob_up) * 100
        
        # Apply rules
        min_confidence = 60  # Threshold
        
        if calib_conf < min_confidence:
            no_trades += 1
            continue
        
        # If we trade, calculate position size and risk
        current_price = row['Close']
        atr = row['ATR']
        
        # SL distance = 2 * ATR
        sl_distance = 2 * atr
        tp_distance = sl_distance * 2.5  # 2.5:1 R:R
        
        # Risk per trade: 0.75% of capital
        risk_pct = 0.0075
        risk_amount = capital * risk_pct
        lots = risk_amount / (sl_distance * 100)  # XAUUSD: $100 per pip per lot
        lots = max(0.01, min(lots, 10.0))  # Clamp to valid range
        
        if direction == "UP":
            entry = current_price
            sl = current_price - sl_distance
            tp = current_price + tp_distance
        else:
            entry = current_price
            sl = current_price + sl_distance
            tp = current_price - tp_distance
        
        # Look ahead to find exit (next candle or within 5 candles)
        exit_idx = None
        exit_price = None
        result = None
        
        for j in range(idx + 1, min(idx + 6, len(df_clean))):
            future_high = df_clean.iloc[j]['High']
            future_low = df_clean.iloc[j]['Low']
            
            if direction == "UP":
                if future_high >= tp:
                    exit_idx = j
                    exit_price = tp
                    result = "win"
                    break
                elif future_low <= sl:
                    exit_idx = j
                    exit_price = sl
                    result = "loss"
                    break
            else:
                if future_low <= tp:
                    exit_idx = j
                    exit_price = tp
                    result = "win"
                    break
                elif future_high >= sl:
                    exit_idx = j
                    exit_price = sl
                    result = "loss"
                    break
        
        # If no exit in 5 candles, close at market
        if result is None:
            exit_idx = min(idx + 5, len(df_clean) - 1)
            exit_price = df_clean.iloc[exit_idx]['Close']
            if direction == "UP":
                result = "win" if exit_price >= entry else "loss"
            else:
                result = "win" if exit_price <= entry else "loss"
        
        # Calculate P&L
        if result == "win":
            pnl = risk_amount * 2.5  # R:R ratio
            wins += 1
        else:
            pnl = -risk_amount
            losses += 1
        
        capital += pnl
        peak_capital = max(peak_capital, capital)
        current_dd = (peak_capital - capital) / peak_capital
        max_drawdown = max(max_drawdown, current_dd)
        
        trades_log.append({
            'date': date,
            'direction': direction,
            'entry': entry,
            'exit': exit_price,
            'sl': sl,
            'tp': tp,
            'result': result,
            'pnl': pnl,
            'raw_conf': raw_conf,
            'calib_conf': calib_conf,
            'capital': capital
        })
        
        equity_curve.append({'date': date, 'capital': capital})
        
    except Exception as e:
        print(f"Error at {date}: {str(e)}")
        continue

print("=" * 70)
print("BACKTEST RESULTS")
print("=" * 70)
print()

if len(trades_log) > 0:
    trades_df = pd.DataFrame(trades_log)
    
    total_trades = len(trades_df)
    win_rate = wins / total_trades if total_trades > 0 else 0
    total_pnl = trades_df['pnl'].sum()
    avg_trade = total_pnl / total_trades if total_trades > 0 else 0
    
    print(f"📊 PERFORMANCE METRICS:")
    print(f"   Initial Capital: ${initial_capital:,.0f}")
    print(f"   Final Capital: ${capital:,.0f}")
    print(f"   Total Profit/Loss: ${total_pnl:,.0f}")
    print(f"   Return: {(capital - initial_capital) / initial_capital * 100:.2f}%")
    print()
    
    print(f"🎯 TRADE STATISTICS:")
    print(f"   Total Trades: {total_trades}")
    print(f"   Wins: {wins} ({win_rate*100:.1f}%)")
    print(f"   Losses: {losses} ({(1-win_rate)*100:.1f}%)")
    print(f"   Avg Win/Loss: ${avg_trade:,.0f}")
    print(f"   No-Trade Signals Blocked: {no_trades}")
    print()
    
    print(f"⚠️ RISK METRICS:")
    print(f"   Max Drawdown: {max_drawdown*100:.2f}%")
    print(f"   Profit Factor: {trades_df[trades_df['pnl'] > 0]['pnl'].sum() / abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum()) if len(trades_df[trades_df['pnl'] < 0]) > 0 else 'N/A'}")
    print()
    
    print(f"📈 AVERAGE TRADE CHARACTERISTICS:")
    print(f"   Avg Raw Confidence: {trades_df['raw_conf'].mean():.1f}%")
    print(f"   Avg Calibrated Confidence: {trades_df['calib_conf'].mean():.1f}%")
    print(f"   Avg Points per Trade: {abs(trades_df['exit'] - trades_df['entry']).mean():.2f}")
    print()
    
    # Save results
    trades_df.to_csv('backtest_daily_results.csv', index=False)
    print("✅ Results saved to backtest_daily_results.csv")
    
    # Direction analysis
    print(f"\n📍 DIRECTION BREAKDOWN:")
    ups = len(trades_df[trades_df['direction'] == 'UP'])
    downs = len(trades_df[trades_df['direction'] == 'DOWN'])
    up_wr = len(trades_df[(trades_df['direction'] == 'UP') & (trades_df['result'] == 'win')]) / ups if ups > 0 else 0
    down_wr = len(trades_df[(trades_df['direction'] == 'DOWN') & (trades_df['result'] == 'win')]) / downs if downs > 0 else 0
    print(f"   UP trades: {ups} ({up_wr*100:.1f}% win rate)")
    print(f"   DOWN trades: {downs} ({down_wr*100:.1f}% win rate)")
    
else:
    print("❌ No trades generated during backtest period")

print()
print("=" * 70)
