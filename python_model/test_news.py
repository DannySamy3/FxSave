from news_fetcher import NewsFetcher
import json

print("Testing Alpha Vantage News Fetch...")
print("=" * 60)

fetcher = NewsFetcher()
news = fetcher.fetch_alpha_vantage_news()

print(f"\n✓ Fetched {len(news)} articles from Alpha Vantage")

if news:
    print("\nFirst 3 articles:")
    for i, item in enumerate(news[:3], 1):
        print(f"\n{i}. [{item['source']}]")
        print(f"   {item['headline'][:80]}...")
        print(f"   Published: {item['published']}")
        print(f"   High Impact: {item['is_high_impact']}")
else:
    print("\n⚠️  No articles fetched!")
    print("This could mean:")
    print("1. API returned no gold-related articles")
    print("2. API error occurred")
    print("3. Filter is too strict")
