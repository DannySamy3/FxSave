"""Debug where high-impact is coming from"""
import sys
sys.path.insert(0, 'd:/CODE/Gold-Trade/python_model')

from news_fetcher import NewsFetcher
from sentiment_analyzer import SentimentAnalyzer

# The actual headline causing the problem
headline = "investingLive European markets wrap: Dollar steady, metals jump on Venezuela situation"
summary = ""
combined_text = f"{headline} {summary}"

print("=" * 70)
print("Debugging High-Impact Flag")
print("=" * 70)

# Test news_fetcher._is_high_impact
fetcher = NewsFetcher()
fetcher_result = fetcher._is_high_impact(combined_text)
print(f"\n1. NewsFetcher._is_high_impact: {fetcher_result}")

# Test sentiment_analyzer._is_high_impact
analyzer = SentimentAnalyzer()
analyzer_result = analyzer._is_high_impact(combined_text)
print(f"2. SentimentAnalyzer._is_high_impact: {analyzer_result}")

# Show which patterns are matching
print("\n--- Checking patterns ---")
text_lower = combined_text.lower()
for i, pattern in enumerate(analyzer.high_impact_patterns):
    match = pattern.search(text_lower)
    if match:
        print(f"   MATCH Pattern {i}: matched '{match.group()}'")

print(f"\nFinal: Combined = {fetcher_result or analyzer_result}")
