"""
Debug NewsIntegration.refresh_news step by step
"""
import sys
sys.path.insert(0, 'd:/CODE/Gold-Trade/python_model')

from news_integration import NewsIntegration
from news_fetcher import NewsFetcher
from sentiment_analyzer import SentimentAnalyzer
from datetime import datetime
import json

# Load config
with open('d:/CODE/Gold-Trade/python_model/config.json') as f:
    config = json.load(f)

print("=" * 60)
print("Manually walking through NewsIntegration.refresh_news()")
print("=" * 60)

# Create NewsIntegration
ni = NewsIntegration(config)
print(f"max_news_age_minutes: {ni.max_news_age_minutes}")
print(f"_last_fetch_time: {ni._last_fetch_time}")

# Step 1: Simulate refresh_news logic
now = datetime.now()
print(f"\nCurrent time: {now.isoformat()}")

# Check cache (should be None initially)
if ni._last_fetch_time:
    cache_age = (now - ni._last_fetch_time).total_seconds() / 60
    print(f"Cache age: {cache_age:.1f} min")
else:
    print("No cache - will fetch new data")

# Fetch news
print("\n[Fetching news...]")
ni._current_news = ni.news_fetcher.fetch_all_news()
print(f"After fetch: _current_news = {len(ni._current_news)} items")

# Add fetch_timestamp
fetch_time = datetime.now()
for item in ni._current_news:
    if 'fetch_timestamp' not in item:
        item['fetch_timestamp'] = fetch_time.isoformat()

# Filter
print("\n[Filtering stale news...]")
before_filter = len(ni._current_news)
ni._current_news = ni._filter_stale_news(ni._current_news, now)
after_filter = len(ni._current_news)
print(f"Before filter: {before_filter}, After filter: {after_filter}")

# Analyze
print("\n[Analyzing sentiment...]")
ni._analyzed_news = ni.sentiment_analyzer.analyze_news_batch(ni._current_news)
print(f"After analysis: _analyzed_news = {len(ni._analyzed_news)} items")

ni._last_fetch_time = now

print("\n" + "=" * 60)
print(f"FINAL STATE:")
print(f"  _current_news: {len(ni._current_news)}")
print(f"  _analyzed_news: {len(ni._analyzed_news)}")

if ni._analyzed_news:
    print("\n🎉 SUCCESS! First 3 headlines:")
    for h in ni._analyzed_news[:3]:
        print(f"  - {h.get('headline', 'No headline')[:50]}...")
