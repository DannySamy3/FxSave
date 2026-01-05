"""
Debug the _filter_stale_news function directly
"""
import sys
sys.path.insert(0, 'd:/CODE/Gold-Trade/python_model')

from news_fetcher import NewsFetcher
from datetime import datetime
import json

# Load config
with open('d:/CODE/Gold-Trade/python_model/config.json') as f:
    config = json.load(f)

now = datetime.now()
max_news_age_minutes = 1440  # 24 hours

print(f"Current time (local): {now.isoformat()}")
print(f"Max news age: {max_news_age_minutes} minutes")
print("=" * 60)

# Fetch news
fetcher = NewsFetcher()
news_items = fetcher.fetch_all_news()
print(f"\nFetched {len(news_items)} items. Testing filter logic:\n")

fresh_count = 0
stale_count = 0
error_count = 0

for i, item in enumerate(news_items[:10], 1):
    published_str = item.get('published') or item.get('timestamp') or item.get('timestamp_utc') or item.get('time')
    print(f"\n{i}. {item.get('headline', 'No headline')[:50]}...")
    print(f"   Published field: {published_str}")
    
    if not published_str:
        print("   RESULT: DISCARDED (no timestamp)")
        error_count += 1
        continue
    
    try:
        if isinstance(published_str, str):
            if 'T' in published_str:
                timestamp = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
            else:
                timestamp = datetime.fromisoformat(published_str)
        else:
            print(f"   RESULT: DISCARDED (not a string: {type(published_str)})")
            error_count += 1
            continue
        
        if timestamp.tzinfo:
            timestamp = timestamp.replace(tzinfo=None)
        
        age_minutes = (now - timestamp).total_seconds() / 60
        print(f"   Parsed: {timestamp.isoformat()}")
        print(f"   Age: {age_minutes:.1f} minutes ({age_minutes/60:.1f} hours)")
        
        if age_minutes <= max_news_age_minutes:
            print(f"   RESULT: ✅ FRESH (within {max_news_age_minutes} min)")
            fresh_count += 1
        else:
            print(f"   RESULT: ❌ STALE (exceeds {max_news_age_minutes} min)")
            stale_count += 1
            
    except Exception as e:
        print(f"   RESULT: ERROR - {e}")
        error_count += 1

print("\n" + "=" * 60)
print(f"SUMMARY: Fresh={fresh_count}, Stale={stale_count}, Errors={error_count}")
