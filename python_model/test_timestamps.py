from news_fetcher import NewsFetcher
import json
from datetime import datetime

print("Testing Alpha Vantage timestamp parsing...")
print("=" * 60)

fetcher = NewsFetcher()
news = fetcher.fetch_alpha_vantage_news()

if news:
    print(f"\n✓ Fetched {len(news)} articles")
    for i, item in enumerate(news[:3], 1):
        published_str = item.get('published', '')
        print(f"\n{i}. {item['headline'][:50]}...")
        print(f"   Published (raw): {published_str}")
        
        # Try to parse it
        try:
            if isinstance(published_str, str):
                # Alpha Vantage format: 20260105T143000
                if 'T' in published_str and len(published_str) == 15:
                    # Parse YYYYMMDDTHHMMSS format
                    parseddt = datetime.strptime(published_str, '%Y%m%dT%H%M%S')
                    print(f"   Parsed: {parseddt.isoformat()}")
                    age_hours = (datetime.now() - parsed) / 3600
                    print(f"   Age: {age_hours:.1f} hours ago")
                else:
                    parsed = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
                    print(f"   Parsed: {parsed.isoformat()}")
        except Exception as e:
            print(f"   Parse ERROR: {e}")
else:
    print("\n⚠️  No articles fetched!")
