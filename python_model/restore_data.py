#!/usr/bin/env python3
"""Restore and regenerate prediction data after corruption"""

import pandas as pd
import json
import os
from datetime import datetime

print("=" * 70)
print("DATA RESTORATION - Checking Current State")
print("=" * 70)

# Check data file
if os.path.exists('gold_data.csv'):
    df = pd.read_csv('gold_data.csv')
    print(f"\n✓ gold_data.csv found")
    print(f"  Shape: {df.shape}")
    print(f"  Columns: {list(df.columns)}")
    print(f"  Last row: {df.iloc[-1].to_dict()}")
else:
    print("\n✗ gold_data.csv NOT FOUND")

# Check if predict.py is available
if os.path.exists('predict.py'):
    print(f"\n✓ predict.py found (can regenerate predictions)")
else:
    print(f"\n✗ predict.py NOT FOUND")

# Check trained models
models_found = []
for tf in ['1d', '4h', '1h', '30m', '15m']:
    if os.path.exists(f'xgb_{tf}.pkl'):
        models_found.append(tf)

print(f"\n✓ Trained models found: {', '.join(models_found)}")

# Try to regenerate fresh predictions
print("\n" + "=" * 70)
print("ATTEMPTING TO REGENERATE PREDICTIONS")
print("=" * 70)

try:
    # Try importing and running predict
    from predict import generate_predictions
    from data_manager import DataManager
    
    print("\nInitializing data manager...")
    dm = DataManager()
    dm.refresh_data()
    
    print("Data refreshed. Generating predictions...")
    predictions = generate_predictions()
    
    # Check predictions
    if predictions and 'predictions' in predictions:
        print(f"\n✓ Predictions generated successfully!")
        for tf in predictions['predictions']:
            pred = predictions['predictions'][tf]
            if 'error' in pred:
                print(f"  {tf}: ERROR - {pred['error'][:50]}...")
            else:
                print(f"  {tf}: {pred.get('decision', 'UNKNOWN')}")
    else:
        print("\n✗ No predictions returned")
        
except Exception as e:
    print(f"\n✗ Error: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("Restoration attempt complete. Check latest_prediction.json")
print("=" * 70)
