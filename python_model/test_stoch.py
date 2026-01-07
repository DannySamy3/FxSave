import pandas as pd
import yfinance as yf
import ta
import numpy as np

# Download sample data
df = yf.download('GC=F', period='59d', interval='15m', progress=False)
print("Downloaded shape:", df.shape)
print("Columns:", df.columns.tolist())

# Test the problematic line
close = df['Close']
high = df['High']
low = df['Low']

try:
    result = ta.momentum.stoch_signal(high, low, close, window=14, smooth_window=3)
    print("stoch_signal result type:", type(result))
    print("stoch_signal result shape:", result.shape if hasattr(result, 'shape') else len(result))
    print("First few values:", result.head() if hasattr(result, 'head') else result[:5])
except Exception as e:
    print(f"Error with stoch_signal: {e}")
    import traceback
    traceback.print_exc()

# Try stoch instead
print("\nTrying stoch():")
try:
    result = ta.momentum.stoch(high, low, close, window=14, smooth_window=3)
    print("stoch result type:", type(result))
    print("stoch result:", result)
except Exception as e:
    print(f"Error with stoch: {e}")
    import traceback
    traceback.print_exc()
