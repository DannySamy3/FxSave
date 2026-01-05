"""
News Integration Module - Unified News Processing for Gold Trading
Combines news fetching, sentiment analysis, and economic calendar.

This is the main interface for news-aware trading decisions.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from news_fetcher import NewsFetcher, get_news_fetcher
from sentiment_analyzer import SentimentAnalyzer, get_sentiment_analyzer
from economic_calendar import EconomicCalendar, get_economic_calendar
from news_blocker import HighImpactNewsBlocker, get_news_blocker


class NewsIntegration:
    """
    Main interface for news-aware trading.
    
    Combines:
    - Live news fetching
    - Sentiment analysis
    - Economic calendar
    - Trading rule integration
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        
        # Initialize components
        self.news_fetcher = get_news_fetcher(config)
        self.sentiment_analyzer = get_sentiment_analyzer()
        self.economic_calendar = get_economic_calendar()
        self.news_blocker = get_news_blocker(config)
        
        # Configuration
        news_config = self.config.get('news', {})
        self.short_term_hours = news_config.get('short_term_hours', 2)
        self.long_term_hours = news_config.get('long_term_hours', 8)
        self.high_impact_risk_multiplier = news_config.get('high_impact_risk_multiplier', 0.0)
        self.sentiment_confidence_factor = news_config.get('sentiment_confidence_factor', 0.05)
        self.enable_blackouts = news_config.get('enable_blackouts', True)
        self.enable_news_blocking = news_config.get('enable_news_blocking', True)
        
        # News control configuration (TTL enforcement)
        # Default to 1440 min (24 hours) to handle weekend/after-hours when no fresh news is published
        news_control = self.config.get('news_control', {})
        self.max_news_age_minutes = news_control.get('max_news_age_minutes', 1440)
        
        # Cache for current session
        self._current_news = []
        self._analyzed_news = []
        self._last_fetch_time = None
        self._cache_duration_minutes = 10
    
    def refresh_news(self, force: bool = False) -> List[Dict]:
        """
        Fetch and analyze latest news with strict TTL enforcement.
        
        Args:
            force: Force refresh even if cache is fresh
            
        Returns:
            List of analyzed news items (only fresh news)
        """
        now = datetime.now()
        
        # Check cache age - CRITICAL: Clear stale cache
        cache_cleared = False
        if self._last_fetch_time:
            cache_age_minutes = (now - self._last_fetch_time).total_seconds() / 60
            if cache_age_minutes > self.max_news_age_minutes:
                # Cache is stale - clear it
                self._current_news = []
                self._analyzed_news = []
                self._last_fetch_time = None
                cache_cleared = True
                print(f"  ⚠️ News cache cleared (age: {cache_age_minutes:.1f} min > {self.max_news_age_minutes} min)")
        
        # Check cache freshness
        if not force and self._last_fetch_time and not cache_cleared:
            elapsed = (now - self._last_fetch_time).total_seconds() / 60
            if elapsed < self._cache_duration_minutes:
                # Filter out stale news from cached results
                fresh_news = self._filter_stale_news(self._analyzed_news, now)
                if len(fresh_news) < len(self._analyzed_news):
                    print(f"  ⚠️ Filtered {len(self._analyzed_news) - len(fresh_news)} stale news items")
                return fresh_news
        
        print("\n📰 Fetching latest news...")
        
        # Fetch news
        self._current_news = self.news_fetcher.fetch_all_news()
        
        # Add fetch_timestamp to all news items (for true recency validation)
        fetch_time = datetime.now()
        for item in self._current_news:
            if 'fetch_timestamp' not in item:
                item['fetch_timestamp'] = fetch_time.isoformat()
            # Ensure origin_timestamp is set (use published/timestamp as origin)
            if 'origin_timestamp' not in item:
                origin_str = item.get('published') or item.get('timestamp') or item.get('timestamp_utc')
                if origin_str:
                    item['origin_timestamp'] = origin_str
        
        # Filter stale news immediately after fetch
        self._current_news = self._filter_stale_news(self._current_news, now)
        
        # Analyze sentiment (only on fresh news)
        self._analyzed_news = self.sentiment_analyzer.analyze_news_batch(self._current_news)
        
        # Update news blocker with latest news (only LIVE_EVENT classification will create blocks)
        if self.enable_news_blocking:
            self.news_blocker.update_active_blocks(self._current_news, fetch_time=now)
        
        self._last_fetch_time = now
        
        print(f"  ✓ Processed {len(self._analyzed_news)} fresh news items")
        
        return self._analyzed_news
    
    def _filter_stale_news(self, news_items: List[Dict], now: datetime) -> List[Dict]:
        """
        Filter out stale news items based on TTL.
        
        Args:
            news_items: List of news items
            now: Current datetime
            
        Returns:
            List of fresh news items only
        """
        fresh_news = []
        
        for item in news_items:
            # Get timestamp from various possible fields
            published_str = item.get('published') or item.get('timestamp') or item.get('timestamp_utc') or item.get('time')
            
            if not published_str:
                # Missing timestamp - discard
                continue
            
            try:
                # Parse timestamp
                if isinstance(published_str, str):
                    if 'T' in published_str:
                        timestamp = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
                    else:
                        timestamp = datetime.fromisoformat(published_str)
                elif isinstance(published_str, (int, float)):
                    timestamp = datetime.utcfromtimestamp(published_str)
                else:
                    continue
                
                # Ensure timezone-naive
                if timestamp.tzinfo:
                    timestamp = timestamp.replace(tzinfo=None)
                
                # Calculate age
                age_minutes = (now - timestamp).total_seconds() / 60
                
                # Only keep fresh news
                if age_minutes <= self.max_news_age_minutes:
                    fresh_news.append(item)
                    
            except Exception:
                # Invalid timestamp - discard
                continue
        
        return fresh_news
    
    def get_news_assessment(self, timeframe: str = "1h") -> Dict:
        """
        Get comprehensive news assessment for trading.
        
        Args:
            timeframe: Trading timeframe (affects lookback period)
            
        Returns:
            {
                'can_trade': bool,
                'reason': str or None,
                'risk_multiplier': float,
                'sentiment_score': float,
                'sentiment_label': str,
                'news_features': Dict,
                'high_impact_events': List[str],
                'upcoming_events': List[Dict],
                'headlines': List[Dict]
            }
        """
        # Refresh news if needed
        news = self.refresh_news()
        
        # Determine lookback based on timeframe
        if timeframe in ['15m', '30m']:
            lookback_hours = self.short_term_hours
        elif timeframe in ['1h']:
            lookback_hours = 4
        else:  # 4h, 1d
            lookback_hours = self.long_term_hours
        
        # Get aggregated sentiment
        sentiment_agg = self.sentiment_analyzer.aggregate_sentiment(
            news, 
            hours_lookback=lookback_hours
        )
        
        # Get sentiment features for ML
        news_features = self.sentiment_analyzer.get_sentiment_features(
            news,
            short_term_hours=self.short_term_hours,
            long_term_hours=self.long_term_hours
        )
        
        # Get economic calendar assessment
        calendar_risk = self.economic_calendar.get_risk_adjustment(hours_ahead=4)
        
        # Determine trading permission
        can_trade = True
        reason = None
        risk_multiplier = 1.0
        news_block_status = None
        
        # PRIORITY 1: Check high-impact news blocker (NEW v2.2.0) with true recency validation
        news_present = len(news) > 0
        news_cache_cleared = False
        trade_blocked_by_news = False
        news_age_minutes = None
        news_impact = None
        news_classification = 'UNVERIFIED'
        
        if self.enable_news_blocking:
            news_block_status = self.news_blocker.get_block_status()
            
            # Calculate news age for logging (use fetch_timestamp if available, else origin)
            if news:
                now = datetime.now()
                ages = []
                classifications = []
                for item in news:
                    fetch_str = item.get('fetch_timestamp')
                    origin_str = item.get('origin_timestamp') or item.get('published') or item.get('timestamp')
                    
                    # Prefer fetch_timestamp for cache age
                    timestamp_str = fetch_str or origin_str
                    if timestamp_str:
                        try:
                            if isinstance(timestamp_str, str):
                                if 'T' in timestamp_str:
                                    ts = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                else:
                                    ts = datetime.fromisoformat(timestamp_str)
                            else:
                                continue
                            if ts.tzinfo:
                                ts = ts.replace(tzinfo=None)
                            age = (now - ts).total_seconds() / 60
                            ages.append(age)
                        except:
                            pass
                
                news_age_minutes = max(ages) if ages else None
            
            # Check if cache was cleared
            if self._last_fetch_time:
                cache_age = (datetime.now() - self._last_fetch_time).total_seconds() / 60
                if cache_age > self.max_news_age_minutes:
                    news_cache_cleared = True
            
            if news_block_status['is_blocked']:
                # Only LIVE_EVENT classification can block trades
                block_classification = news_block_status.get('classification', 'UNVERIFIED')
                if block_classification == 'LIVE_EVENT':
                    can_trade = False
                    reason = 'HIGH_IMPACT_NEWS'
                    risk_multiplier = 0.0
                    trade_blocked_by_news = True
                    news_impact = news_block_status.get('impact_level', 'HIGH')
                    news_classification = block_classification
                    
                    # Return early with standardized wording and TTL info
                    return {
                        'can_trade': False,
                        'reason': reason,
                        'risk_multiplier': 0.0,
                        'sentiment_score': sentiment_agg['aggregate_score'],
                        'sentiment_label': sentiment_agg['aggregate_label'],
                        'news_features': news_features,
                        'high_impact_events': [news_block_status.get('headline', 'High-impact news')],
                        'upcoming_events': calendar_risk['upcoming_high_impact'],
                        'headlines': self._get_formatted_headlines(news[:10]),
                        'bullish_count': sentiment_agg['bullish_count'],
                        'bearish_count': sentiment_agg['bearish_count'],
                        'neutral_count': sentiment_agg['neutral_count'],
                        'sample_size': sentiment_agg['sample_size'],
                        'news_block_status': news_block_status,  # Include block details
                        # TTL logging fields (enhanced for true recency validation)
                        'news_present': news_present,
                        'news_age_minutes': news_age_minutes,
                        'news_impact': news_impact,
                        'news_cache_cleared': news_cache_cleared,
                        'trade_blocked_by_news': trade_blocked_by_news,
                        'news_classification': news_classification,
                        'news_origin_timestamp': news_block_status.get('origin_timestamp'),
                        'news_fetch_timestamp': news_block_status.get('fetch_timestamp'),
                        'cache_age_minutes': news_block_status.get('cache_age_minutes')
                    }
                else:
                    # STALE_CONTEXT, EXPIRED, or UNVERIFIED cannot block
                    # Fail-safe: proceed as if no high-impact news exists
                    news_classification = block_classification
                    # Continue with normal processing (no block)
        
        # Check calendar blackout
        if self.enable_blackouts and calendar_risk['in_blackout']:
            can_trade = False
            reason = f"CALENDAR_BLACKOUT: {calendar_risk['reason']}"
            risk_multiplier = 0.0
        
        # Check high impact news (legacy check - now handled by news blocker above)
        elif sentiment_agg['has_high_impact']:
            if self.high_impact_risk_multiplier == 0:
                can_trade = False
                reason = f"HIGH_IMPACT_NEWS: {sentiment_agg['high_impact_headlines'][0][:50]}"
                risk_multiplier = 0.0
            else:
                risk_multiplier = min(risk_multiplier, self.high_impact_risk_multiplier)
                reason = "HIGH_IMPACT_NEWS_CAUTION"
        
        # Check upcoming high impact events
        elif calendar_risk['upcoming_high_impact']:
            risk_multiplier = min(risk_multiplier, calendar_risk['risk_multiplier'])
            if risk_multiplier <= 0:
                can_trade = False
                reason = f"EVENT_IMMINENT: {calendar_risk['reason']}"
        
        # Apply calendar risk multiplier
        risk_multiplier = min(risk_multiplier, calendar_risk['risk_multiplier'])
        
        # Calculate news age for logging (if not already done)
        if news_age_minutes is None and news:
            now = datetime.now()
            ages = []
            for item in news:
                published_str = item.get('published') or item.get('timestamp') or item.get('timestamp_utc')
                if published_str:
                    try:
                        if isinstance(published_str, str):
                            if 'T' in published_str:
                                ts = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
                            else:
                                ts = datetime.fromisoformat(published_str)
                        else:
                            continue
                        if ts.tzinfo:
                            ts = ts.replace(tzinfo=None)
                        age = (now - ts).total_seconds() / 60
                        ages.append(age)
                    except:
                        pass
            news_age_minutes = max(ages) if ages else None
        
        result = {
            'can_trade': can_trade,
            'reason': reason,
            'risk_multiplier': round(risk_multiplier, 2),
            'sentiment_score': sentiment_agg['aggregate_score'],
            'sentiment_label': sentiment_agg['aggregate_label'],
            'news_features': news_features,
            'high_impact_events': sentiment_agg['high_impact_headlines'],
            'upcoming_events': calendar_risk['upcoming_high_impact'],
            'headlines': self._get_formatted_headlines(news[:10]),
            'bullish_count': sentiment_agg['bullish_count'],
            'bearish_count': sentiment_agg['bearish_count'],
            'neutral_count': sentiment_agg['neutral_count'],
            'sample_size': sentiment_agg['sample_size'],
            # TTL logging fields
            'news_present': news_present,
            'news_age_minutes': round(news_age_minutes, 1) if news_age_minutes else None,
            'news_impact': news_impact,
            'news_cache_cleared': news_cache_cleared,
            'trade_blocked_by_news': trade_blocked_by_news
        }
        
        # Include news block status if available
        if news_block_status:
            result['news_block_status'] = news_block_status
        
        return result
    
    def _get_formatted_headlines(self, news: List[Dict]) -> List[Dict]:
        """Format headlines for display"""
        formatted = []
        for item in news:
            formatted.append({
                'source': item.get('source', 'Unknown'),
                'headline': item.get('headline', ''),
                'sentiment': item.get('sentiment_label', 'NEUTRAL'),
                'sentiment_score': item.get('sentiment_score', 0),
                'is_high_impact': item.get('is_high_impact', False),
                'published': item.get('published', '')
            })
        return formatted
    
    def adjust_confidence(self, base_confidence: float, 
                         direction: str,
                         sentiment_score: float) -> float:
        """
        Optionally adjust confidence based on news sentiment.
        
        If sentiment aligns with direction, slight boost.
        If sentiment conflicts, slight reduction.
        
        Args:
            base_confidence: Original calibrated confidence
            direction: 'UP' or 'DOWN'
            sentiment_score: -1 to 1 (negative = bearish, positive = bullish)
            
        Returns:
            Adjusted confidence (still bounded 0-1)
        """
        if self.sentiment_confidence_factor == 0:
            return base_confidence
        
        # Determine alignment
        if direction == 'UP':
            # Bullish prediction - positive sentiment aligns
            alignment = sentiment_score
        else:
            # Bearish prediction - negative sentiment aligns
            alignment = -sentiment_score
        
        # Calculate adjustment
        adjustment = alignment * self.sentiment_confidence_factor
        
        # Apply with bounds
        adjusted = base_confidence + adjustment
        adjusted = max(0.0, min(1.0, adjusted))
        
        return round(adjusted, 4)
    
    def get_trade_decision(self, timeframe: str,
                          base_direction: str,
                          base_confidence: float,
                          base_decision: str,
                          base_reason: str = None) -> Dict:
        """
        Make final trade decision incorporating news.
        
        Args:
            timeframe: Trading timeframe
            base_direction: ML model direction
            base_confidence: Calibrated confidence
            base_decision: 'TRADE' or 'NO_TRADE' from rules engine
            base_reason: Reason if NO_TRADE
            
        Returns:
            {
                'decision': str,
                'reason': str,
                'direction': str,
                'confidence': float,
                'risk_multiplier': float,
                'news_sentiment': float,
                'news_label': str,
                'high_impact': bool,
                'headlines': List
            }
        """
        # Get news assessment
        assessment = self.get_news_assessment(timeframe)
        
        # Start with base decision
        decision = base_decision
        reason = base_reason
        risk_multiplier = 1.0
        
        # If base decision is already NO_TRADE, keep it
        if base_decision == 'NO_TRADE':
            return {
                'decision': 'NO_TRADE',
                'reason': base_reason,
                'direction': base_direction,
                'confidence': base_confidence,
                'risk_multiplier': 0.0,
                'news_sentiment': assessment['sentiment_score'],
                'news_label': assessment['sentiment_label'],
                'high_impact': len(assessment['high_impact_events']) > 0,
                'headlines': assessment['headlines']
            }
        
        # Check if news blocks trading
        if not assessment['can_trade']:
            return {
                'decision': 'NO_TRADE',
                'reason': assessment['reason'],
                'direction': base_direction,
                'confidence': base_confidence,
                'risk_multiplier': 0.0,
                'news_sentiment': assessment['sentiment_score'],
                'news_label': assessment['sentiment_label'],
                'high_impact': True,
                'headlines': assessment['headlines']
            }
        
        # Adjust confidence based on sentiment
        adjusted_confidence = self.adjust_confidence(
            base_confidence,
            base_direction,
            assessment['sentiment_score']
        )
        
        # Apply risk multiplier from news
        risk_multiplier = assessment['risk_multiplier']
        
        return {
            'decision': 'TRADE',
            'reason': None,
            'direction': base_direction,
            'confidence': adjusted_confidence,
            'risk_multiplier': risk_multiplier,
            'news_sentiment': assessment['sentiment_score'],
            'news_label': assessment['sentiment_label'],
            'high_impact': len(assessment['high_impact_events']) > 0,
            'headlines': assessment['headlines']
        }
    
    def save_news_state(self, output_dir: str = None):
        """Save current news state for UI/API consumption"""
        output_dir = Path(output_dir) if output_dir else Path(__file__).parent
        
        assessment = self.get_news_assessment()
        
        state = {
            'timestamp': datetime.now().isoformat(),
            'can_trade': assessment['can_trade'],
            'block_reason': assessment['reason'],
            'sentiment': {
                'score': assessment['sentiment_score'],
                'label': assessment['sentiment_label'],
                'bullish_count': assessment['bullish_count'],
                'bearish_count': assessment['bearish_count'],
                'neutral_count': assessment['neutral_count']
            },
            'risk_multiplier': assessment['risk_multiplier'],
            'high_impact_events': assessment['high_impact_events'],
            'upcoming_events': [
                {
                    'name': e.get('name'),
                    'time': e.get('time'),
                    'impact': e.get('impact')
                }
                for e in assessment.get('upcoming_events', [])
            ],
            'headlines': assessment['headlines'][:10]
        }
        
        # Include news block status if available
        if 'news_block_status' in assessment:
            block_status = assessment['news_block_status']
            state['news_block'] = {
                'is_blocked': block_status['is_blocked'],
                'news_event': block_status.get('news_event'),
                'impact_level': block_status.get('impact_level'),
                'minutes_remaining': block_status.get('minutes_remaining'),
                'cooldown_minutes': block_status.get('cooldown_minutes'),
                'details': block_status.get('details'),
                'ui_wording': block_status.get('ui_wording')
            }
        
        output_path = output_dir / 'news_state.json'
        with open(output_path, 'w') as f:
            json.dump(state, f, indent=2, default=str)
        
        # Also save news blocker state
        if self.enable_news_blocking:
            blocker_state_path = output_dir / 'news_blocker_state.json'
            self.news_blocker.save_state(str(blocker_state_path))
        
        return state


# Singleton instance
_news_integration = None

def get_news_integration(config: Dict = None) -> NewsIntegration:
    """Get or create singleton NewsIntegration"""
    global _news_integration
    if _news_integration is None or config:
        _news_integration = NewsIntegration(config)
    return _news_integration


if __name__ == "__main__":
    # Test news integration
    print("=" * 60)
    print("News Integration Test")
    print("=" * 60)
    
    # Create with test config
    config = {
        'news': {
            'short_term_hours': 4,
            'long_term_hours': 12,
            'high_impact_risk_multiplier': 0.0,  # Block on high impact
            'sentiment_confidence_factor': 0.05,
            'enable_blackouts': True
        }
    }
    
    integration = NewsIntegration(config)
    
    # Get assessment
    print("\n📊 Getting news assessment...")
    assessment = integration.get_news_assessment(timeframe='1h')
    
    print(f"\n✅ Can Trade: {assessment['can_trade']}")
    print(f"📈 Sentiment: {assessment['sentiment_score']:+.3f} ({assessment['sentiment_label']})")
    print(f"⚠️ Risk Multiplier: {assessment['risk_multiplier']:.2f}")
    print(f"🔴 High Impact: {len(assessment['high_impact_events'])} events")
    
    print(f"\n📰 Latest Headlines:")
    for h in assessment['headlines'][:5]:
        impact = "🔴" if h['is_high_impact'] else "⚪"
        sent = "↑" if h['sentiment'] == 'BULLISH' else ("↓" if h['sentiment'] == 'BEARISH' else "→")
        print(f"   {impact} {sent} {h['headline'][:60]}...")
    
    # Test trade decision
    print("\n\n🎯 Testing Trade Decision:")
    decision = integration.get_trade_decision(
        timeframe='1h',
        base_direction='UP',
        base_confidence=0.65,
        base_decision='TRADE'
    )
    
    print(f"   Decision: {decision['decision']}")
    print(f"   Direction: {decision['direction']}")
    print(f"   Confidence: {decision['confidence']:.2%}")
    print(f"   Risk Mult: {decision['risk_multiplier']:.2f}")
    
    # Save state
    integration.save_news_state()
    print("\n✓ Saved news_state.json")




