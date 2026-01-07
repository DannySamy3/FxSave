"""
News API Key Configuration Helper
Helps configure API keys for Finnhub, Alpha Vantage, and NewsAPI.
"""

import json
import os
from pathlib import Path

def configure_news_keys():
    """Interactive script to configure news API keys"""
    config_path = Path(__file__).parent / 'config.json'
    
    # Load current config
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    news_config = config.get('news', {})
    api_keys = news_config.get('api_keys', {})
    
    print("=" * 60)
    print("News API Key Configuration")
    print("=" * 60)
    print("\nEnter API keys (press Enter to skip/keep existing):")
    print("(Keys can also be set via environment variables)")
    print()
    
    # Check environment variables first
    env_keys = {
        'finnhub': os.getenv('FINNHUB_API_KEY', ''),
        'alpha_vantage': os.getenv('ALPHA_VANTAGE_API_KEY', ''),
        'newsapi': os.getenv('NEWSAPI_KEY', '')
    }
    
    # Finnhub
    current_finnhub = api_keys.get('finnhub', '') or env_keys['finnhub']
    if current_finnhub:
        print(f"Finnhub API Key: [CURRENT: {current_finnhub[:8]}...] (hidden)")
    else:
        print("Finnhub API Key: [NOT SET]")
    finnhub_input = input("  Enter new Finnhub key (or press Enter to keep): ").strip()
    if finnhub_input:
        api_keys['finnhub'] = finnhub_input
    elif not current_finnhub:
        api_keys['finnhub'] = env_keys['finnhub'] if env_keys['finnhub'] else ''
    
    # Alpha Vantage
    current_av = api_keys.get('alpha_vantage', '') or env_keys['alpha_vantage']
    if current_av:
        print(f"\nAlpha Vantage API Key: [CURRENT: {current_av[:8]}...] (hidden)")
    else:
        print("\nAlpha Vantage API Key: [NOT SET]")
    av_input = input("  Enter new Alpha Vantage key (or press Enter to keep): ").strip()
    if av_input:
        api_keys['alpha_vantage'] = av_input
    elif not current_av:
        api_keys['alpha_vantage'] = env_keys['alpha_vantage'] if env_keys['alpha_vantage'] else ''
    
    # NewsAPI
    current_newsapi = api_keys.get('newsapi', '') or env_keys['newsapi']
    if current_newsapi:
        print(f"\nNewsAPI Key: [CURRENT: {current_newsapi[:8]}...] (hidden)")
    else:
        print("\nNewsAPI Key: [NOT SET]")
    newsapi_input = input("  Enter new NewsAPI key (or press Enter to keep): ").strip()
    if newsapi_input:
        api_keys['newsapi'] = newsapi_input
    elif not current_newsapi:
        api_keys['newsapi'] = env_keys['newsapi'] if env_keys['newsapi'] else ''
    
    # Update config
    news_config['api_keys'] = api_keys
    config['news'] = news_config
    
    # Save
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print("\n" + "=" * 60)
    print("Configuration saved!")
    print("=" * 60)
    
    # Summary
    configured = sum(1 for k, v in api_keys.items() if v)
    print(f"\nAPI Keys Configured: {configured}/3")
    if configured == 3:
        print("✓ All news sources configured")
    elif configured > 0:
        print(f"⚠ {3 - configured} key(s) still missing - news integration will use fallback")
    else:
        print("⚠ No keys configured - news integration will use fallback/mock data")
    
    print("\nNote: You can also set keys via environment variables:")
    print("  FINNHUB_API_KEY=your_key")
    print("  ALPHA_VANTAGE_API_KEY=your_key")
    print("  NEWSAPI_KEY=your_key")

if __name__ == "__main__":
    configure_news_keys()








