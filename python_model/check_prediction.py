import json

with open('d:/CODE/Gold-Trade/public/latest_prediction.json', 'r') as f:
    data = json.load(f)

news = data.get('news', {})
print(f"News section found: {news is not None}")
print(f"Headlines count: {len(news.get('headlines', []))}")
print(f"Can trade: {news.get('can_trade', 'N/A')}")
print(f"Sentiment score: {news.get('sentiment_score', 'N/A')}")
print(f"Sentiment label: {news.get('sentiment_label', 'N/A')}")

if news.get('headlines'):
    print(f"\n✅ Headlines ARE present! Showing first 3:")
    for i, h in enumerate(news['headlines'][:3], 1):
        print(f"\n{i}. [{h.get('source', 'Unknown')}]")
        print(f"   {h.get('headline', 'No headline')[:70]}...")
        print(f"   Published: {h.get('published', 'Unknown')}")
        print(f"   High Impact: {h.get('is_high_impact', 'Unknown')}")
else:
    print("\n❌ No headlines in prediction file!")
