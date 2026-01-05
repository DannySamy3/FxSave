"""Test Finnhub Economic Calendar API"""
import os
import sys
sys.path.insert(0, 'd:/CODE/Gold-Trade/python_model')

from dotenv import load_dotenv
from pathlib import Path
load_dotenv(dotenv_path=Path('d:/CODE/Gold-Trade/python_model/.env'))

import requests
from datetime import datetime, timedelta

api_key = os.environ.get('FINNHUB_API_KEY')
print(f"Finnhub API Key: {api_key[:10]}..." if api_key else "No API key!")

# Test economic calendar endpoint
# From docs, the endpoint is /calendar/economic
url = 'https://finnhub.io/api/v1/calendar/economic'
from_date = datetime.now().strftime('%Y-%m-%d')
to_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')

params = {
    'from': from_date,
    'to': to_date,
    'token': api_key
}

print(f"\nFetching economic calendar: {from_date} to {to_date}")
response = requests.get(url, params=params, timeout=10)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    events = data.get('economicCalendar', [])
    print(f"\n✅ Got {len(events)} economic events!")
    
    # Show first few events
    for i, event in enumerate(events[:10], 1):
        country = event.get('country', '')
        event_name = event.get('event', '')
        impact = event.get('impact', '')
        time = event.get('time', '')
        estimate = event.get('estimate', '')
        prev = event.get('prev', '')
        actual = event.get('actual', '')
        print(f"\n{i}. [{country}] {time}")
        print(f"   Event: {event_name}")
        print(f"   Impact: {impact}, Estimate: {estimate}, Prev: {prev}, Actual: {actual}")
    
    # Filter for USD only
    usd_events = [e for e in events if e.get('country') == 'US']
    print(f"\n\n📊 USD-only events: {len(usd_events)}")
else:
    print(f"Error: {response.text}")
