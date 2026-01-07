import pandas as pd
import yfinance as yf

# Download sample data
df = yf.download('GC=F', period='59d', interval='15m', progress=False)
print("Type of df:", type(df))
print("Index type:", type(df.index))
print("Columns:", df.columns)
print("Column types:", type(df.columns))
print("\nFirst few rows:")
print(df.head())

# Check if MultiIndex
if isinstance(df.columns, pd.MultiIndex):
    print("\nIt's a MultiIndex! Flattening...")
    df.columns = df.columns.get_level_values(1)
    print("After flattening:")
    print(df.head())
    
    # Check Close
    close = df['GC=F']
    print("\nClose shape:", close.shape)
    print("Close type:", type(close))
    print("First few values:", close.head())
