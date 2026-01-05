"""
News Fetcher Module - Live Financial News for Gold Trading
Fetches news from multiple sources: Finnhub, Alpha Vantage, NewsAPI

Features:
- Multi-source news aggregation
- Gold/USD keyword filtering
- Rate limiting and caching
- Fallback to cached data when offline
"""

import os
import json
import time
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
import requests
from typing import List, Dict, Optional
import warnings

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Load .env from the same directory as this script
    env_path = Path(__file__).parent / '.env'
    load_dotenv(dotenv_path=env_path)
except ImportError:
    # python-dotenv not installed, will use system environment variables
    pass

warnings.filterwarnings('ignore')


# API Configuration (set these as environment variables or in config)
DEFAULT_CONFIG = {
    'finnhub_api_key': os.environ.get('FINNHUB_API_KEY', ''),
    'alpha_vantage_key': os.environ.get('ALPHA_VANTAGE_KEY', ''),
    'newsapi_key': os.environ.get('NEWSAPI_KEY', ''),
    'cache_duration_minutes': 15,
    'request_timeout': 10,
    'max_headlines': 20
}

# Gold and USD related keywords for filtering (affects XAUUSD trading)
GOLD_USD_KEYWORDS = [
    # Gold specific
    'gold', 'xauusd', 'xau/usd', 'precious metal', 'bullion',
    'gold price', 'gold futures', 'comex gold', 'spot gold',
    'gold demand', 'gold supply', 'central bank gold',
    # USD/Forex specific (CRITICAL for XAUUSD)
    'dollar', 'usd', 'dxy', 'dollar index', 'greenback',
    'forex', 'fx', 'currency', 'exchange rate',
    # Central banks & rates (major USD movers)
    'fed', 'federal reserve', 'fomc', 'interest rate', 'rate decision',
    'rate hike', 'rate cut', 'hawkish', 'dovish', 'monetary policy',
    'powell', 'fed chair', 'fed meeting',
    # Economic data (USD movers)
    'inflation', 'cpi', 'pce', 'consumer price', 
    'unemployment', 'non-farm', 'nfp', 'payroll', 'jobs report',
    'gdp', 'retail sales', 'ism', 'pmi',
    # Treasury/yields (inverse gold correlation)
    'treasury', 'yield', 'bond', 't-bill', '10-year', '2-year',
    # Safe haven flows
    'geopolitical', 'war', 'conflict', 'sanctions',
    'safe haven', 'risk off', 'risk on', 'risk appetite'
]

# XAUUSD High-Impact Events ONLY
# These events DIRECTLY and SIGNIFICANTLY move Gold/USD price
# Removed: ECB, BoE, BoJ (don't directly affect XAUUSD)
XAUUSD_HIGH_IMPACT_KEYWORDS = [
    # US Federal Reserve (THE most important for XAUUSD)
    'fed rate', 'fomc decision', 'fomc meeting', 'fomc statement',
    'fed decision', 'powell speaks', 'powell speech', 'fed chair',
    'fed hike', 'fed cut', 'fed pause', 'fed pivot',
    'rate hike', 'rate cut', 'rate decision', 'interest rate decision',
    # US Economic Data (Major USD movers)
    'non-farm payroll', 'nonfarm payroll', 'nfp report', 'jobs report',
    'us cpi', 'cpi report', 'inflation report', 'pce inflation',
    'us gdp', 'gdp report', 'us unemployment rate',
    # Dollar-specific shocks
    'dollar crash', 'dollar surge', 'dollar plunge', 'dxy surge',
    # Gold-specific events
    'gold surge', 'gold crash', 'gold plunge', 'gold rally',
    'central bank gold', 'gold reserves', 'gold buying',
    # Geopolitical (safe-haven triggers for Gold)
    'war outbreak', 'military strike', 'invasion', 'nuclear',
    'sanctions russia', 'sanctions china', 'trade war',
    # Market crisis (flight to Gold)
    'market crash', 'financial crisis', 'bank collapse', 'default',
    'recession confirmed', 'emergency rate',
]

# Commentary patterns that should NOT be marked as high impact
# v2.2.1: These patterns indicate market interpretation, not official announcements
COMMENTARY_PATTERNS = [
    'signals potential', 'signals possible', 'signals likely',
    'hints at', 'suggests', 'may pause', 'could cut', 'might hike',
    'analyst says', 'economist expects', 'strategist believes',
    'amid cooling', 'amid rising', 'amid slowing',
    'potential rate', 'potential pause',
]

# USD-ONLY keywords - For filtering news that affects USD/Dollar specifically
# These directly impact XAUUSD (Gold vs US Dollar) trading
USD_ONLY_KEYWORDS = [
    # US Dollar direct mentions
    'dollar', 'usd', 'dxy', 'dollar index', 'greenback', 'us dollar',
    'buck',  # slang for dollar
    # US Federal Reserve
    'fed', 'federal reserve', 'fomc', 'powell', 'fed chair',
    'fed meeting', 'fed rate', 'fed policy', 'fed decision',
    # US Economic Data
    'us inflation', 'us cpi', 'us pce', 'us gdp', 'us economy',
    'us jobs', 'us payroll', 'nonfarm', 'non-farm', 'nfp',
    'us unemployment', 'us retail', 'us consumer',
    'us treasury', 'us yield', 'us bond',
    # General US terms (must contain "us" or "american")
    'united states', 'america', 'american',
]


class NewsCache:
    """Simple file-based cache for news data"""
    
    def __init__(self, cache_dir: str = None):
        self.cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / 'cache' / 'news'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_path(self, key: str) -> Path:
        hash_key = hashlib.md5(key.encode()).hexdigest()[:12]
        return self.cache_dir / f'{hash_key}.json'
    
    def get(self, key: str, max_age_minutes: int = 15) -> Optional[Dict]:
        """Get cached data if not expired"""
        path = self._get_cache_path(key)
        
        if not path.exists():
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            cached_time = datetime.fromisoformat(data.get('cached_at', '2000-01-01'))
            if datetime.now() - cached_time > timedelta(minutes=max_age_minutes):
                return None
            
            return data.get('content')
        except:
            return None
    
    def set(self, key: str, content: any):
        """Cache data with timestamp"""
        path = self._get_cache_path(key)
        
        data = {
            'cached_at': datetime.now().isoformat(),
            'key': key,
            'content': content
        }
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
    
    def clear_old(self, max_age_hours: int = 24):
        """Remove old cache files"""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        for file in self.cache_dir.glob('*.json'):
            if file.stat().st_mtime < cutoff.timestamp():
                file.unlink()


class NewsFetcher:
    """
    Aggregates news from multiple financial news sources.
    Filters for Gold/USD related news.
    """
    
    def __init__(self, config: Dict = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.cache = NewsCache()
        self._last_request_time = {}
    
    def _rate_limit(self, source: str, min_interval: float = 1.0):
        """Simple rate limiting per source"""
        last_time = self._last_request_time.get(source, 0)
        elapsed = time.time() - last_time
        
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        
        self._last_request_time[source] = time.time()
    
    def _is_gold_usd_related(self, text: str) -> bool:
        """Check if text contains Gold/USD related keywords that impact XAUUSD trading"""
        text_lower = text.lower()
        return any(kw in text_lower for kw in GOLD_USD_KEYWORDS)
    
    def _is_high_impact(self, text: str) -> bool:
        """
        Check if news is HIGH IMPACT for XAUUSD specifically.
        Only flags events that genuinely and significantly move Gold/USD price.
        Excludes: ECB, BoE, BoJ, generic market news
        """
        text_lower = text.lower()
        
        # Check for commentary patterns first - these are NOT high impact
        if any(pattern in text_lower for pattern in COMMENTARY_PATTERNS):
            return False
        
        # Only flag if it matches XAUUSD-specific high impact events
        return any(kw in text_lower for kw in XAUUSD_HIGH_IMPACT_KEYWORDS)
    
    def _is_usd_only(self, text: str) -> bool:
        """
        Check if text is specifically about USD/Dollar.
        Filters out GBP, EUR, JPY, etc. news that doesn't affect XAUUSD.
        """
        text_lower = text.lower()
        return any(kw in text_lower for kw in USD_ONLY_KEYWORDS)
    
    def fetch_finnhub(self) -> List[Dict]:
        """
        Fetch forex/currency news from Finnhub.io
        Uses Market News API with category=forex for USD-relevant news
        Free tier: 60 calls/minute
        """
        api_key = self.config.get('finnhub_api_key')
        if not api_key:
            print("  ⚠️ Finnhub API key not configured")
            return []
        
        cache_key = 'finnhub_forex_news'
        cached = self.cache.get(cache_key, self.config['cache_duration_minutes'])
        if cached:
            return cached
        
        try:
            self._rate_limit('finnhub')
            
            # Fetch forex/currency news - directly relevant to XAUUSD trading
            url = 'https://finnhub.io/api/v1/news'
            params = {
                'category': 'forex',  # Forex category for USD/currency news
                'token': api_key
            }
            
            response = requests.get(url, params=params, timeout=self.config['request_timeout'])
            
            if response.status_code != 200:
                print(f"  ⚠️ Finnhub API error: {response.status_code}")
                return []
            
            news_items = response.json()
            
            if not news_items:
                print("  ⚠️ Finnhub: No forex news returned")
                return []
            
            # Filter for USD-ONLY news (not GBP, EUR, JPY, etc.)
            # Only USD affects XAUUSD trading
            filtered = []
            usd_count = 0
            for item in news_items:
                headline = item.get('headline', '')
                summary = item.get('summary', '')
                combined_text = f"{headline} {summary}"
                source = item.get('source', 'Finnhub')
                
                # CRITICAL: Only include USD-related news for XAUUSD trading
                if not self._is_usd_only(combined_text):
                    continue  # Skip non-USD news (GBP, EUR, JPY, etc.)
                
                usd_count += 1
                
                # Convert UNIX timestamp to ISO format
                unix_time = item.get('datetime', 0)
                try:
                    published_iso = datetime.fromtimestamp(unix_time).isoformat() if unix_time else ''
                except:
                    published_iso = ''
                
                filtered.append({
                    'source': f'Finnhub ({source})',
                    'headline': headline,
                    'summary': summary[:200] if summary else '',
                    'url': item.get('url', ''),
                    'published': published_iso,
                    'is_high_impact': self._is_high_impact(combined_text),
                    'category': 'USD/Forex'
                })
            
            self.cache.set(cache_key, filtered)
            print(f"  ✓ Finnhub: {usd_count} USD-related articles (filtered from {len(news_items)} forex news)")
            return filtered
            
        except Exception as e:
            print(f"  ❌ Finnhub fetch error: {e}")
            return []
    
    def fetch_alpha_vantage_news(self) -> List[Dict]:
        """
        Fetch news from Alpha Vantage News Sentiment API
        Focuses on economy_monetary topic for Fed/central bank/gold-relevant news
        """
        api_key = self.config.get('alpha_vantage_key')
        if not api_key:
            return []
        
        cache_key = 'alphavantage_gold_news'
        cached = self.cache.get(cache_key, self.config['cache_duration_minutes'])
        if cached:
            return cached
        
        try:
            self._rate_limit('alphavantage', 12)  # 5 calls/minute free tier
            
            url = 'https://www.alphavantage.co/query'
            params = {
                'function': 'NEWS_SENTIMENT',
                'tickers': 'FOREX:USD',  # USD currency news - directly impacts XAUUSD
                'topics': 'economy_monetary,forex',  # Fed, rates, forex news
                'apikey': api_key,
                'limit': 50,
                'sort': 'LATEST'
            }
            
            response = requests.get(url, params=params, timeout=self.config['request_timeout'])
            
            if response.status_code != 200:
                print(f"  ⚠️ Alpha Vantage API response code: {response.status_code}")
                return []
            
            data = response.json()
            
            # Alpha Vantage returns articles directly in 'feed' key
            if 'feed' not in data or not data['feed']:
                print(f"  ⚠️ Alpha Vantage: No 'feed' in response or empty feed")
                return []
            
            filtered = []
            for item in data['feed']:
                headline = item.get('title', '')
                summary = item.get('summary', '')
                combined_text = f"{headline} {summary}"
                
                # Include all USD/forex/economy news since they all impact XAUUSD
                # Alpha Vantage already filtered by FOREX:USD ticker and forex/economy topics
                if True:  # Keep all articles from FOREX:USD + economy_monetary + forex topics
                    # Get source name from authors list or use Alpha Vantage
                    source_name = 'AlphaVantage'
                    if item.get('authors'):
                        source_name = f"AlphaVantage ({item['authors'][0]})"
                    elif item.get('source'):
                        source_name = f"AlphaVantage ({item['source']})"
                    
                    # Parse Alpha Vantage timestamp format: 20260105T143000 -> ISO format
                    published_raw = item.get('time_published', '')
                    published_iso = published_raw
                    try:
                        if published_raw and 'T' in published_raw and len(published_raw) == 15:
                            # Convert YYYYMMDDTHHMMSS to YYYY-MM-DDTHH:MM:SS
                            dt = datetime.strptime(published_raw, '%Y%m%dT%H%M%S')
                            published_iso = dt.isoformat()
                    except Exception as e:
                        print(f"  ⚠️ Timestamp parse warning: {e}")
                    
                    filtered.append({
                        'source': source_name,
                        'headline': headline,
                        'summary': summary[:200] if summary else '',
                        'url': item.get('url', ''),
                        'published': published_iso,
                        'is_high_impact': self._is_high_impact(combined_text),
                        'av_sentiment': item.get('overall_sentiment_score', 0)
                    })
            
            self.cache.set(cache_key, filtered)
            print(f"  ✓ Alpha Vantage: {len(filtered)} gold-related articles from {len(data['feed'])} total")
            return filtered
            
        except Exception as e:
            print(f"  ❌ Alpha Vantage fetch error: {e}")
            return []
    
    def fetch_newsapi(self) -> List[Dict]:
        """
        Fetch news from NewsAPI.org
        Free tier: 100 requests/day
        """
        api_key = self.config.get('newsapi_key')
        if not api_key:
            return []
        
        cache_key = 'newsapi_gold_news'
        cached = self.cache.get(cache_key, self.config['cache_duration_minutes'])
        if cached:
            return cached
        
        try:
            self._rate_limit('newsapi', 1)
            
            url = 'https://newsapi.org/v2/everything'
            params = {
                'q': '(gold OR XAUUSD OR "gold price") AND (USD OR dollar OR Fed)',
                'language': 'en',
                'sortBy': 'publishedAt',
                'pageSize': 20,
                'apiKey': api_key
            }
            
            response = requests.get(url, params=params, timeout=self.config['request_timeout'])
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            
            if data.get('status') != 'ok':
                return []
            
            filtered = []
            for item in data.get('articles', []):
                headline = item.get('title', '')
                description = item.get('description', '')
                
                filtered.append({
                    'source': f"NewsAPI ({item.get('source', {}).get('name', 'Unknown')})",
                    'headline': headline,
                    'summary': description[:200] if description else '',
                    'url': item.get('url', ''),
                    'published': item.get('publishedAt', ''),
                    'is_high_impact': self._is_high_impact(f"{headline} {description}")
                })
            
            self.cache.set(cache_key, filtered)
            return filtered
            
        except Exception as e:
            print(f"  ❌ NewsAPI fetch error: {e}")
            return []
    
    def fetch_mock_news(self) -> List[Dict]:
        """
        Generate mock news for testing when no API keys available.
        In production, remove or disable this.
        """
        # Current date: January 5, 2026
        now = datetime.now()
        
        mock_news = [
            {
                'source': 'Mock Bloomberg',
                'headline': 'Gold holds steady near $2,650 as investors assess Fed outlook',
                'summary': 'Spot gold trades in tight range as markets digest economic data and central bank commentary...',
                'url': '#',
                'published': (now - timedelta(minutes=25)).isoformat(),
                'is_high_impact': False
            },
            {
                'source': 'Mock Reuters',
                'headline': 'Dollar retreats from weekly highs, supporting precious metals',
                'summary': 'The U.S. dollar index pulled back from its highest level this week, providing support for gold and silver prices...',
                'url': '#',
                'published': (now - timedelta(hours=1, minutes=15)).isoformat(),
                'is_high_impact': False
            },
            {
                'source': 'Mock Financial Times',
                'headline': 'Asian central banks add 45 tonnes to gold reserves in December',
                'summary': 'Central banks in emerging markets continued their diversification strategy with steady gold purchases...',
                'url': '#',
                'published': (now - timedelta(hours=2, minutes=40)).isoformat(),
                'is_high_impact': False
            },
            {
                'source': 'Mock MarketWatch',
                'headline': 'Treasury yields inch higher ahead of jobs report',
                'summary': '10-year Treasury yields rose 3 basis points as investors position ahead of Friday\'s employment data...',
                'url': '#',
                'published': (now - timedelta(hours=3, minutes=10)).isoformat(),
                'is_high_impact': False
            },
            {
                'source': 'Mock WSJ',
                'headline': 'Geopolitical tensions keep safe-haven demand for gold elevated',
                'summary': 'Ongoing uncertainties in global trade and regional conflicts continue to underpin gold demand...',
                'url': '#',
                'published': (now - timedelta(hours=5, minutes=30)).isoformat(),
                'is_high_impact': False
            }
        ]
        return mock_news
    
    def fetch_all_news(self, use_mock_fallback: bool = True) -> List[Dict]:
        """
        Fetch and aggregate news from all available sources.
        
        Args:
            use_mock_fallback: If True, use mock data when no API keys configured
            
        Returns:
            List of news items sorted by publish time
        """
        all_news = []
        
        # Try each source
        finnhub_news = self.fetch_finnhub()
        if finnhub_news:
            all_news.extend(finnhub_news)
            print(f"  📰 Finnhub: {len(finnhub_news)} articles")
        
        av_news = self.fetch_alpha_vantage_news()
        if av_news:
            all_news.extend(av_news)
            print(f"  📰 AlphaVantage: {len(av_news)} articles")
        
        newsapi_news = self.fetch_newsapi()
        if newsapi_news:
            all_news.extend(newsapi_news)
            print(f"  📰 NewsAPI: {len(newsapi_news)} articles")
        
        # Fallback to mock if no news and allowed
        if not all_news and use_mock_fallback:
            all_news = self.fetch_mock_news()
            print(f"  📰 Using mock news: {len(all_news)} articles")
        
        # Sort by publish time (newest first)
        def get_time(item):
            try:
                return datetime.fromisoformat(item.get('published', '2000-01-01').replace('Z', '+00:00'))
            except:
                return datetime(2000, 1, 1)
        
        all_news.sort(key=get_time, reverse=True)
        
        # Limit total
        return all_news[:self.config['max_headlines']]
    
    def get_recent_news(self, hours: int = 4) -> List[Dict]:
        """Get news from the last N hours"""
        all_news = self.fetch_all_news()
        cutoff = datetime.now() - timedelta(hours=hours)
        
        recent = []
        for item in all_news:
            try:
                pub_time = datetime.fromisoformat(item.get('published', '2000-01-01').replace('Z', '+00:00'))
                if pub_time.replace(tzinfo=None) > cutoff:
                    recent.append(item)
            except:
                pass
        
        return recent
    
    def has_high_impact_news(self, hours: int = 2) -> tuple:
        """
        Check if there's high-impact news in the recent period.
        
        Returns:
            (has_high_impact: bool, headlines: List[str])
        """
        recent = self.get_recent_news(hours)
        
        high_impact = [n for n in recent if n.get('is_high_impact', False)]
        
        return len(high_impact) > 0, [n['headline'] for n in high_impact]


# Singleton instance
_news_fetcher_instance = None

def get_news_fetcher(config: Dict = None) -> NewsFetcher:
    """Get or create singleton NewsFetcher"""
    global _news_fetcher_instance
    if _news_fetcher_instance is None:
        _news_fetcher_instance = NewsFetcher(config)
    return _news_fetcher_instance


if __name__ == "__main__":
    # Test the news fetcher
    print("=" * 50)
    print("News Fetcher Test")
    print("=" * 50)
    
    fetcher = NewsFetcher()
    news = fetcher.fetch_all_news()
    
    print(f"\nFetched {len(news)} articles:")
    for i, item in enumerate(news[:5], 1):
        impact = "🔴 HIGH IMPACT" if item.get('is_high_impact') else ""
        print(f"\n{i}. [{item['source']}] {impact}")
        print(f"   {item['headline'][:80]}...")
    
    has_impact, headlines = fetcher.has_high_impact_news(hours=4)
    print(f"\nHigh impact news in last 4h: {has_impact}")
    if headlines:
        for h in headlines:
            print(f"  - {h[:60]}...")





