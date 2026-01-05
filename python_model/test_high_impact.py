"""Test XAUUSD High-Impact Filter"""
import sys
sys.path.insert(0, 'd:/CODE/Gold-Trade/python_model')

# Test headlines
test_headlines = [
    # Should be HIGH IMPACT (XAUUSD specific)
    "FOMC decision: Fed holds rates steady, signals no cuts in 2026",
    "Non-farm payroll report shows US added 275K jobs in December",
    "US CPI report shows inflation cooling to 2.9%",
    "Powell speech: Fed chair signals rate cut pause until March",
    "Gold surge as markets flee to safe haven amid crisis",
    "Dollar crash: DXY plunges 2% on weak GDP data",
    
    # Should NOT be high impact (non-XAUUSD)
    "UK net mortgage approvals fell slightly in November",
    "ECB cuts rates for third time this year",
    "Bank of Japan maintains ultra-loose policy",
    "Dollar steady, metals jump on Venezuela situation",
    "European markets close higher on earnings",
    "BoE holds rates, inflation concerns persist",
]

from news_fetcher import NewsFetcher

fetcher = NewsFetcher()

print("=" * 70)
print("XAUUSD High-Impact Filter Test")
print("=" * 70)
print("\nExpected: Only US Fed, US data, Gold, Dollar shocks = HIGH IMPACT")
print("-" * 70)

for headline in test_headlines:
    is_high = fetcher._is_high_impact(headline)
    symbol = "🔴 HIGH" if is_high else "⚪ low"
    print(f"{symbol}: {headline[:60]}...")
