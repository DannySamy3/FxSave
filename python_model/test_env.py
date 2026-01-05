from dotenv import load_dotenv
from pathlib import Path
import os

env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

api_key = os.environ.get('ALPHA_VANTAGE_KEY', 'NOT FOUND')
print(f"API Key loaded: {api_key[:15] if api_key != 'NOT FOUND' else 'NOT FOUND'}...")
print(f"Full env path: {env_path}")
print(f"Env file exists: {env_path.exists()}")

# Now test the news fetcher
from news_fetcher import NewsFetcher
fetcher = NewsFetcher()
print(f"\nNewsFetcher config alpha_vantage_key: {fetcher.config.get('alpha_vantage_key', 'MISSING')[:15]}...")
