"""Test Free Economic Calendar APIs"""
import requests
from datetime import datetime, timedelta

# Method 1: Try Investing.com web scraping approach
# This is a popular open-source solution

# Method 2: Try TradingEconomics (limited free)
# https://api.tradingeconomics.com/calendar

# Method 3: Try Financial Modeling Prep free tier
# https://financialmodelingprep.com/api/v3/economic_calendar

print("Testing Economic Calendar APIs...")
print("=" * 60)

# Test 1: FMP Economic Calendar (free tier)
print("\n1. Testing Financial Modeling Prep...")
# FMP requires API key, but has free tier
# Get one at: https://financialmodelingprep.com/developer/docs/

from_date = datetime.now().strftime('%Y-%m-%d')
to_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')

# Using demo key for test
fmp_url = f"https://financialmodelingprep.com/api/v3/economic_calendar?from={from_date}&to={to_date}&apikey=demo"
try:
    resp = requests.get(fmp_url, timeout=10)
    print(f"   FMP Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   Events: {len(data) if isinstance(data, list) else 'N/A'}")
        if data and isinstance(data, list):
            for e in data[:3]:
                print(f"   - {e}")
except Exception as e:
    print(f"   Error: {e}")

# Test 2: Alternative - use web scraping from ForexFactory
# This is what most traders use
print("\n2. Forex Factory scraping approach...")
print("   (Would require web scraping - more complex but most reliable)")

# Test 3: Try TradingView widget embedding
# Could embed TradingView's economic calendar widget directly
print("\n3. TradingView Widget (embed approach)...")
print("   (Can embed TradingView's calendar widget directly in frontend)")
