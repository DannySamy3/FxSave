"""
Debug Backtest - Check Model Predictions
"""

import pandas as pd
import numpy as np
import pickle
from features import compute_indicators

df = pd.read_csv('gold_data.csv')
df['Date'] = pd.to_datetime(df['Date'])
df = df.sort_values('Date')
df = df[df['Date'] >= '2023-01-01'].reset_index(drop=True)
df = df.set_index(pd.to_datetime(df['Date']))
df = df[df['Date'] >= '2023-01-01']

df = compute_indicators(df)

model = pickle.load(open('xgb_1d.pkl', 'rb'))
calibrator = pickle.load(open('calibrator_1d.pkl', 'rb'))

features = [
    'Close', 'High', 'Low', 'Open', 'Volume',
    'EMA_10', 'EMA_50', 'RSI', 'ATR',
    'MACD', 'MACD_Signal', 'MACD_Hist',
    'Price_to_EMA10', 'Price_to_EMA50'
]

df_clean = df.dropna(subset=features)

print("Analyzing model predictions...")
print()

confs = []
for i in range(min(100, len(df_clean))):
    row = df_clean.iloc[i]
    X = row[features].values.reshape(1, -1)
    
    prob = model.predict_proba(X)[0][1]
    prob_cal = calibrator.predict([[prob]])[0]
    
    direction = "UP" if prob >= 0.5 else "DOWN"
    conf_raw = (prob if prob >= 0.5 else 1-prob) * 100
    conf_cal = (prob_cal if prob >= 0.5 else 1-prob_cal) * 100
    
    confs.append(conf_cal)
    if i < 20:
        print(f"{i}: {direction} Raw={conf_raw:.1f}% Cal={conf_cal:.1f}%")

print()
print(f"Avg Confidence: {np.mean(confs):.1f}%")
print(f"Min Confidence: {np.min(confs):.1f}%")
print(f"Max Confidence: {np.max(confs):.1f}%")
print(f"Median Confidence: {np.median(confs):.1f}%")
print()
print(f"Trades above 60%: {sum(1 for c in confs if c >= 60)} / {len(confs)}")
print(f"Trades above 55%: {sum(1 for c in confs if c >= 55)} / {len(confs)}")
print(f"Trades above 50%: {sum(1 for c in confs if c >= 50)} / {len(confs)}")
