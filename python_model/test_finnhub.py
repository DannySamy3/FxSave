"""Test Finnhub Forex News API"""
import os
import sys
sys.path.insert(0, 'd:/CODE/Gold-Trade/python_model')

# Load env
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(dotenv_path=Path('d:/CODE/Gold-Trade/python_model/.env'))

import requests
from datetime import datetime

api_key = os.environ.get('FINNHUB_API_KEY')
print(f"Finnhub API Key: {api_key[:10]}..." if api_key else "No API key!")

# Test forex category
url = 'https://finnhub.io/api/v1/news'
params = {
    'category': 'forex',
    'token': api_key
}

print(f"\nFetching: {url}?category=forex")
response = requests.get(url, params=params, timeout=10)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    news = response.json()
    print(f"\n✅ Got {len(news)} forex news articles!")
    
    for i, item in enumerate(news[:5], 1):
        headline = item.get('headline', '')[:60]
        source = item.get('source', 'Unknown')
        unix_time = item.get('datetime', 0)
        dt = datetime.fromtimestamp(unix_time) if unix_time else None
        print(f"\n{i}. [{source}]")
        print(f"   {headline}...")
        print(f"   Time: {dt.isoformat() if dt else 'Unknown'}")
else:
    print(f"Error: {response.text}")
