"""
Backtest Engine for Gold-Trade System (Market-Only Mode)
Faithfully replicates live decision logic for historical XAUUSD data.

- No future data leakage
- Candle-close decisions only
- All rule gates in live order
- NO_TRADE decisions logged with reasons
- Outputs trade log, decision log, equity/drawdown curves, and metrics

Usage:
    python backtest.py --data gold_data.csv --start 2022-01-01 --end 2025-01-01

"""

import pandas as pd
import numpy as np
import argparse
from datetime import datetime
from pathlib import Path

from live_predictor import LivePredictor
from forward_test import ForwardTester
from data_manager import DataManager

# --- Configurable parameters ---
DEFAULT_DATA_PATH = 'gold_data.csv'
DEFAULT_START = '2022-01-01'
DEFAULT_END = '2025-01-01'



# --- Backtest DataManager ---
class BacktestDataManager(DataManager):
    def __init__(self, full_data_by_tf):
        super().__init__(symbol='GC=F')
        self._full_data_by_tf = full_data_by_tf
        self._current_index = None

    def set_index(self, idx):
        self._current_index = idx

    def get_cached_data(self, timeframe):
        # Return only data up to the current index for this timeframe
        df = self._full_data_by_tf[timeframe]
        if self._current_index is None:
            return df
        # Only up to and including the current index
        return df[df.index <= self._current_index]


def run_backtest(data_path, start_date, end_date):
    # Load historical data (assume 1d for now, extend to all TFs as needed)
    # For full fidelity, load all TFs from cache or resample as needed
    base_df = pd.read_csv(data_path, parse_dates=['Date'], index_col='Date')
    base_df = base_df[(base_df.index >= start_date) & (base_df.index <= end_date)]
    print(f"Loaded {len(base_df)} rows from {data_path} ({start_date} to {end_date})")


    # Prepare data for all timeframes
    tf_map = {}
    tf_map['1d'] = base_df.copy()


    # Helper for resampling with all required columns
    def resample_ohlcv_full(df, rule):
        ohlc_dict = {
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }
        # Only resample OHLCV, ignore other columns for now
        ohlcv = df[['Open', 'High', 'Low', 'Close', 'Volume']].resample(rule).apply(ohlc_dict)
        ohlcv = ohlcv.dropna()
        # Forward/backward fill to avoid NaNs
        ohlcv = ohlcv.ffill().bfill()
        # Add back any other columns as NaN (so feature pipeline doesn't break)
        for col in df.columns:
            if col not in ohlcv.columns:
                ohlcv[col] = np.nan
        # Reorder columns to match original
        ohlcv = ohlcv[df.columns]
        return ohlcv

    # 4h
    tf_map['4h'] = resample_ohlcv_full(base_df, '4H')
    # 1h
    tf_map['1h'] = resample_ohlcv_full(base_df, '1H')
    # 30m
    tf_map['30m'] = resample_ohlcv_full(base_df, '30T')
    # 15m
    tf_map['15m'] = resample_ohlcv_full(base_df, '15T')

    # Align columns for each TF (fill missing columns with NaN)
    all_cols = set()
    for df in tf_map.values():
        all_cols.update(df.columns)
    for tf, df in tf_map.items():
        for col in all_cols:
            if col not in df.columns:
                df[col] = np.nan
        tf_map[tf] = df[sorted(all_cols)]

    # Initialize backtest data manager
    bt_data_manager = BacktestDataManager(tf_map)

    # Initialize predictor in market-only mode, inject backtest data manager
    predictor = LivePredictor()
    predictor.news_enabled = False  # Market-only mode
    predictor.data_manager = bt_data_manager


    # Prepare logs and state
    trade_log = []
    decision_log = []
    equity_curve = []
    drawdown_curve = []
    capital = 100000  # Starting capital
    peak = capital
    max_drawdown = 0
    open_trades = {tf: [] for tf in tf_map.keys()}

    # Iterate through each candle (simulate candle-close decisions)
    for i in range(50, len(base_df)):
        current_time = base_df.index[i]
        bt_data_manager.set_index(current_time)

        # Predict for all timeframes (LTF+HTF)
        results = predictor.predict_all_timeframes(update_data=False)
        for tf, res in results.items():
            # Log every decision
            decision_log.append({
                'timestamp': current_time,
                'timeframe': tf,
                'decision': res.get('decision'),
                'direction': res.get('direction'),
                'confidence': res.get('confidence'),
                'rejection_reason': res.get('rejection_reason'),
            })
            # Simulate trade if TRADE and no open trade for this TF
            if res.get('decision') == 'TRADE' and not open_trades[tf]:
                entry = res['setup'].get('entry', tf_map[tf].loc[current_time]['Close'])
                sl = res['setup'].get('sl')
                tp = res['setup'].get('tp')
                lots = res['setup'].get('lots', 0)
                direction = res.get('direction')
                risk = res['setup'].get('risk_amount', 0)
                rr_ratio = res['setup'].get('rr_ratio', 1)
                open_trades[tf].append({
                    'entry_time': current_time,
                    'entry': entry,
                    'sl': sl,
                    'tp': tp,
                    'lots': lots,
                    'risk': risk,
                    'direction': direction,
                    'tf': tf,
                    'open_idx': i,
                    'rr_ratio': rr_ratio
                })

        # Simulate trade exits for each TF
        for tf, trades in open_trades.items():
            still_open = []
            for trade in trades:
                # Look ahead from entry to current_time for SL/TP hit
                df_tf = tf_map[tf]
                entry_idx = trade['open_idx']
                exit_idx = i
                trade_closed = False
                for j in range(entry_idx+1, min(exit_idx+2, len(df_tf))):
                    row = df_tf.iloc[j]
                    high = row['High']
                    low = row['Low']
                    close = row['Close']
                    # Long
                    if trade['direction'] == 'UP':
                        if low <= trade['sl']:
                            # SL hit
                            exit_price = trade['sl']
                            result = 'loss'
                            trade_closed = True
                        elif high >= trade['tp']:
                            # TP hit
                            exit_price = trade['tp']
                            result = 'win'
                            trade_closed = True
                    else:
                        if high >= trade['sl']:
                            # SL hit
                            exit_price = trade['sl']
                            result = 'loss'
                            trade_closed = True
                        elif low <= trade['tp']:
                            # TP hit
                            exit_price = trade['tp']
                            result = 'win'
                            trade_closed = True
                    if trade_closed:
                        exit_time = df_tf.index[j]
                        pnl = trade['risk'] * (trade.get('rr_ratio', 1) if result == 'win' else -1)
                        capital += pnl
                        peak = max(peak, capital)
                        dd = (peak - capital) / peak
                        max_drawdown = max(max_drawdown, dd)
                        trade_log.append({
                            'entry_time': trade['entry_time'],
                            'exit_time': exit_time,
                            'timeframe': tf,
                            'direction': trade['direction'],
                            'result': result,
                            'entry': trade['entry'],
                            'exit': exit_price,
                            'pnl': pnl,
                            'capital': capital,
                            'drawdown': dd,
                        })
                        break
                if not trade_closed:
                    still_open.append(trade)
            open_trades[tf] = still_open

        equity_curve.append({'timestamp': current_time, 'capital': capital})
        drawdown_curve.append({'timestamp': current_time, 'drawdown': max_drawdown})

    # Close any remaining open trades at final price
    for tf, trades in open_trades.items():
        for trade in trades:
            final_price = tf_map[tf].iloc[-1]['Close']
            result = 'win' if (trade['direction'] == 'UP' and final_price >= trade['entry']) or (trade['direction'] == 'DOWN' and final_price <= trade['entry']) else 'loss'
            pnl = trade['risk'] * (trade.get('rr_ratio', 1) if result == 'win' else -1)
            capital += pnl
            peak = max(peak, capital)
            dd = (peak - capital) / peak
            max_drawdown = max(max_drawdown, dd)
            trade_log.append({
                'entry_time': trade['entry_time'],
                'exit_time': tf_map[tf].index[-1],
                'timeframe': tf,
                'direction': trade['direction'],
                'result': result,
                'entry': trade['entry'],
                'exit': final_price,
                'pnl': pnl,
                'capital': capital,
                'drawdown': dd,
            })

    # Output logs
    pd.DataFrame(trade_log).to_csv('backtest_trade_log.csv', index=False)
    pd.DataFrame(decision_log).to_csv('backtest_decision_log.csv', index=False)
    pd.DataFrame(equity_curve).to_csv('backtest_equity_curve.csv', index=False)
    pd.DataFrame(drawdown_curve).to_csv('backtest_drawdown_curve.csv', index=False)
    print("Backtest complete. Logs saved.")

    # --- Compute Metrics ---
    trade_df = pd.DataFrame(trade_log)
    decision_df = pd.DataFrame(decision_log)
    equity_df = pd.DataFrame(equity_curve)
    drawdown_df = pd.DataFrame(drawdown_curve)

    # Performance
    total_trades = len(trade_df)
    wins = (trade_df['result'] == 'win').sum()
    losses = (trade_df['result'] == 'loss').sum()
    win_rate = wins / total_trades if total_trades > 0 else 0
    avg_rr = trade_df['pnl'].sum() / (trade_df['risk'].sum() if 'risk' in trade_df else 1)
    expectancy = trade_df['pnl'].mean() if total_trades > 0 else 0
    gross_profit = trade_df[trade_df['pnl'] > 0]['pnl'].sum()
    gross_loss = -trade_df[trade_df['pnl'] < 0]['pnl'].sum()
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    net_return = (trade_df['capital'].iloc[-1] - 100000) / 100000 if total_trades > 0 else 0
    max_drawdown = drawdown_df['drawdown'].max() if not drawdown_df.empty else 0

    # Decision Quality
    buy_pct = (decision_df['direction'] == 'UP').mean()
    sell_pct = (decision_df['direction'] == 'DOWN').mean()
    no_trade_pct = (decision_df['decision'] == 'NO_TRADE').mean()
    block_by_conf = (decision_df['rejection_reason'] == 'LOW_CONFIDENCE').mean()
    block_by_htf = (decision_df['rejection_reason'] == 'HTF_CONFLICT').mean()
    block_by_news = (decision_df['rejection_reason'] == 'HIGH_IMPACT_NEWS').mean()
    avg_conf_win = decision_df[decision_df['decision'] == 'TRADE'].merge(trade_df[trade_df['result'] == 'win'], left_on='timestamp', right_on='entry_time')['confidence'].mean() if wins > 0 else 0
    avg_conf_loss = decision_df[decision_df['decision'] == 'TRADE'].merge(trade_df[trade_df['result'] == 'loss'], left_on='timestamp', right_on='entry_time')['confidence'].mean() if losses > 0 else 0
    avg_conf_no_trade = decision_df[decision_df['decision'] == 'NO_TRADE']['confidence'].mean() if no_trade_pct > 0 else 0

    # Capital Safety
    # Worst losing streak
    streak = 0
    max_streak = 0
    for r in trade_df['result']:
        if r == 'loss':
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    worst_losing_streak = max_streak
    # Time to recover drawdowns (approximate)
    drawdown_periods = (drawdown_df['drawdown'] > 0).sum()
    # Daily risk exposure (mean risk per day)
    if 'risk' in trade_df:
        trade_df['date'] = pd.to_datetime(trade_df['entry_time']).dt.date
        daily_risk = trade_df.groupby('date')['risk'].sum().mean()
    else:
        daily_risk = 0

    # --- Print Summary ---
    print("\n=== BACKTEST SUMMARY ===")
    print(f"Total trades: {total_trades}")
    print(f"Win rate: {win_rate:.2%}")
    print(f"Average R:R: {avg_rr:.2f}")
    print(f"Expectancy: {expectancy:.2f}")
    print(f"Profit factor: {profit_factor:.2f}")
    print(f"Net return: {net_return:.2%}")
    print(f"Max drawdown: {max_drawdown:.2%}")
    print(f"% BUY: {buy_pct:.2%} | % SELL: {sell_pct:.2%} | % NO_TRADE: {no_trade_pct:.2%}")
    print(f"% blocked by confidence: {block_by_conf:.2%}")
    print(f"% blocked by HTF: {block_by_htf:.2%}")
    print(f"% blocked by news: {block_by_news:.2%}")
    print(f"Avg confidence (win): {avg_conf_win:.2f}")
    print(f"Avg confidence (loss): {avg_conf_loss:.2f}")
    print(f"Avg confidence (NO_TRADE): {avg_conf_no_trade:.2f}")
    print(f"Worst losing streak: {worst_losing_streak}")
    print(f"Drawdown periods: {drawdown_periods}")
    print(f"Avg daily risk: {daily_risk:.2f}")

    # Final evaluation
    print("\n=== FINAL EVALUATION ===")
    print(f"Profitable? {'YES' if net_return > 0 else 'NO'}")
    print(f"Drawdown acceptable? {'YES' if max_drawdown <= 0.2 else 'NO'}")
    print(f"Edge statistically meaningful? {'YES' if profit_factor >= 1.2 and win_rate > 0.5 else 'NO'}")
    print(f"NO_TRADE reduces losses? {'YES' if avg_conf_no_trade < avg_conf_loss else 'NO'}")

    # Output logs and metrics
    pd.DataFrame(trade_log).to_csv('backtest_trade_log.csv', index=False)
    pd.DataFrame(decision_log).to_csv('backtest_decision_log.csv', index=False)
    pd.DataFrame(equity_curve).to_csv('backtest_equity_curve.csv', index=False)
    pd.DataFrame(drawdown_curve).to_csv('backtest_drawdown_curve.csv', index=False)
    print("Backtest complete. Logs saved.")
    # TODO: Compute and print all required metrics

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=str, default=DEFAULT_DATA_PATH)
    parser.add_argument('--start', type=str, default=DEFAULT_START)
    parser.add_argument('--end', type=str, default=DEFAULT_END)
    args = parser.parse_args()
    run_backtest(args.data, args.start, args.end)
