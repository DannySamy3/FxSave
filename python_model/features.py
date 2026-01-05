"""
Feature Engineering Module for Gold Price Prediction.
Shared logic for training and inference to ensure consistency.
"""
import pandas as pd
import numpy as np
import ta

def compute_indicators(df):
    """
    Compute wealth of technical indicators for Gold Price Prediction.
    
    Args:
        df: DataFrame with OHLCV data
        
    Returns:
        DataFrame with added feature columns
    """
    df = df.copy()
    
    # Ensure columns are present and correct type
    close = df['Close']
    high = df['High']
    low = df['Low']
    volume = df['Volume'] if 'Volume' in df.columns else None
    
    # 1. Trend Indicators
    # EMAs
    df['EMA_10'] = ta.trend.ema_indicator(close, window=10)
    df['EMA_20'] = ta.trend.ema_indicator(close, window=20)
    df['EMA_50'] = ta.trend.ema_indicator(close, window=50)
    df['EMA_200'] = ta.trend.ema_indicator(close, window=200)
    
    # SMAs
    df['SMA_20'] = ta.trend.sma_indicator(close, window=20)
    df['SMA_50'] = ta.trend.sma_indicator(close, window=50)
    
    # ADX (Average Directional Index) - Strength of trend
    df['ADX'] = ta.trend.adx(high, low, close, window=14)
    
    # MACD
    macd = ta.trend.MACD(close)
    df['MACD'] = macd.macd()
    df['MACD_Signal'] = macd.macd_signal()
    df['MACD_Hist'] = macd.macd_diff()
    
    # Ichimoku (simplified)
    # df['Ichimoku_A'] = ta.trend.ichimoku_a(high, low)
    # df['Ichimoku_B'] = ta.trend.ichimoku_b(high, low)

    # 2. Momentum Indicators
    # RSI
    df['RSI'] = ta.momentum.rsi(close, window=14)
    
    # Stochastic Oscillator
    df['Stoch_K'] = ta.momentum.stoch(high, low, close, window=14, smooth_window=3)
    df['Stoch_D'] = ta.momentum.stoch_signal(high, low, close, window=14, smooth_window=3)
    
    # ROC (Rate of Change)
    df['ROC'] = ta.momentum.roc(close, window=12)
    
    # TSI (True Strength Index)
    df['TSI'] = ta.momentum.tsi(close, window_slow=25, window_fast=13)

    # 3. Volatility Indicators
    # ATR
    df['ATR'] = ta.volatility.average_true_range(high, low, close, window=14)
    
    # Bollinger Bands
    bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    df['BB_High'] = bb.bollinger_hband()
    df['BB_Low'] = bb.bollinger_lband()
    df['BB_Width'] = bb.bollinger_wband()
    df['BB_P'] = bb.bollinger_pband() # %B
    
    # Keltner Channels (using EMA 20 +/- 2*ATR)
    df['KC_High'] = df['EMA_20'] + (2 * df['ATR'])
    df['KC_Low'] = df['EMA_20'] - (2 * df['ATR'])
    
    # 4. Volume Indicators (if volume available)
    if volume is not None and not volume.empty:
        # OBV
        try:
             df['OBV'] = ta.volume.on_balance_volume(close, volume)
        except:
             # Fallback if volume is all zero or invalid
             df['OBV'] = 0
             
        # MFI (Money Flow Index)
        try:
            df['MFI'] = ta.volume.money_flow_index(high, low, close, volume, window=14)
        except:
            df['MFI'] = 50
    else:
        df['OBV'] = 0
        df['MFI'] = 50

    # 5. Price Action / Custom Features
    # Distance from key averages
    df['Dist_EMA50'] = (close - df['EMA_50']) / df['EMA_50'] * 100
    df['Dist_EMA200'] = (close - df['EMA_200']) / df['EMA_200'] * 100
    
    # Candlestick Body/Shadows
    df['Body_Size'] = abs(close - df['Open'])
    df['Shadow_Upper'] = high - df[['Open', 'Close']].max(axis=1)
    df['Shadow_Lower'] = df[['Open', 'Close']].min(axis=1) - low
    
    # 6. Time Features
    # (Useful for capturing session volatility: London/NY open)
    df['Hour'] = df.index.hour
    df['DayOfWeek'] = df.index.dayofweek
    
    # Shift-based features (Lagged values)
    # Return of past 1, 3, 5 candles
    df['Ret_1'] = df['Close'].pct_change(1)
    df['Ret_3'] = df['Close'].pct_change(3)
    
    return df.dropna()

def get_feature_columns():
    """Return list of column names used for training"""
    return [
        'EMA_10', 'EMA_20', 'EMA_50', 'EMA_200', 'SMA_20', 'SMA_50', 'ADX',
        'MACD', 'MACD_Signal', 'MACD_Hist',
        'RSI', 'Stoch_K', 'Stoch_D', 'ROC', 'TSI',
        'ATR', 'BB_Width', 'BB_P', 'KC_High', 'KC_Low',
        'OBV', 'MFI',
        'Dist_EMA50', 'Dist_EMA200',
        'Body_Size', 'Shadow_Upper', 'Shadow_Lower',
        'Hour', 'DayOfWeek', 'Ret_1', 'Ret_3'
    ]
