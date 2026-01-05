from news_fetcher import NewsFetcher
from datetime import datetime

print("Checking Alpha Vantage news timestamps...")
print("=" * 60)

fetcher = NewsFetcher()
news = fetcher.fetch_alpha_vantage_news()

now = datetime.now()
print(f"\nCurrent time: {now.isoformat()}")
print(f"\nFetched {len(news)} articles. Analyzing timestamps:\n")

ages = []
for i, item in enumerate(news[:10], 1):
    published_str = item.get('published', '')
    print(f"{i}. Published: {published_str}")
    try:
        if 'T' in published_str:
            pub_dt = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
            if pub_dt.tzinfo:
                pub_dt = pub_dt.replace(tzinfo=None)
            age_hours = (now - pub_dt).total_seconds() / 3600
            age_minutes = (now - pub_dt).total_seconds() / 60
            ages.append(age_minutes)
            print(f"   Age: {age_hours:.1f} hours ({age_minutes:.0f} minutes)")
    except Exception as e:
        print(f"   Parse error: {e}")

if ages:
    print(f"\n" + "=" * 60)
    print(f"SUMMARY:")
    print(f"  Oldest news: {max(ages):.0f} minutes ({max(ages)/60:.1f} hours)")
    print(f"  Newest news: {min(ages):.0f} minutes ({min(ages)/60:.1f} hours)")
    print(f"\n  Recommended max_news_age_minutes: {int(max(ages)) + 60}")
