"""
Debug script to trace the exact news data flow
"""
import sys
sys.path.insert(0, 'd:/CODE/Gold-Trade/python_model')

from news_integration import get_news_integration
from news_fetcher import NewsFetcher
import json

# Load config
with open('d:/CODE/Gold-Trade/python_model/config.json') as f:
    config = json.load(f)

print("=" * 60)
print("DEBUG: Tracing news data flow")
print("=" * 60)

# Step 1: Direct Alpha Vantage fetch
print("\n[STEP 1] Direct fetch from Alpha Vantage...")
fetcher = NewsFetcher() 
av_news = fetcher.fetch_alpha_vantage_news()
print(f"  ✓ Alpha Vantage returned: {len(av_news)} articles")

# Step 2: Full fetch (includes mock fallback)
print("\n[STEP 2] Full fetch (fetch_all_news)...")
all_news = fetcher.fetch_all_news()
print(f"  ✓ Total fetched: {len(all_news)} articles")

# Step 3: Integration layer
print("\n[STEP 3] NewsIntegration.refresh_news()...")
news_integration = get_news_integration(config)
news = news_integration.refresh_news(force=True)
print(f"  ✓ After refresh_news(): {len(news)} articles")

# Step 4: Get assessment
print("\n[STEP 4] NewsIntegration.get_news_assessment()...")
assessment = news_integration.get_news_assessment('1h')
headlines = assessment.get('headlines', [])
print(f"  ✓ Headlines in assessment: {len(headlines)}")

if headlines:
    print("\n🎉 SUCCESS! Headlines found:")
    for h in headlines[:3]:
        print(f"  - [{h.get('source')}] {h.get('headline', '')[:50]}...")
else:
    print("\n❌ PROBLEM: No headlines in assessment!")
    print(f"  Can trade: {assessment.get('can_trade')}")
    print(f"  Sentiment: {assessment.get('sentiment_score')}")
    
    # Check internal state
    print("\n  Internal state debug:")
    print(f"  _current_news: {len(news_integration._current_news)}")
    print(f"  _analyzed_news: {len(news_integration._analyzed_news)}")
