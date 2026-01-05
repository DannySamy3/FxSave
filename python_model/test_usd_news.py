"""Test USD-only news filter"""
import sys
sys.path.insert(0, 'd:/CODE/Gold-Trade/python_model')

from news_fetcher import NewsFetcher

print("=" * 60)
print("Testing USD-Only News Filter")
print("=" * 60)

fetcher = NewsFetcher()
news = fetcher.fetch_finnhub()

print(f"\nFiltered USD-only news: {len(news)} articles")
print("-" * 60)

for i, item in enumerate(news[:10], 1):
    headline = item.get('headline', '')[:70]
    source = item.get('source', '')
    impact = "🔴 HIGH" if item.get('is_high_impact') else "⚪"
    print(f"\n{i}. {impact} [{source}]")
    print(f"   {headline}...")

if not news:
    print("\n❌ No USD-specific news found in current forex feed.")
    print("   This may happen on weekends/low-activity periods.")
