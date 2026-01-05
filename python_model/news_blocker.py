"""
High-Impact News Handling Module (v2.2.0)
Implements time-based cooldown and volatility confirmation for major macro events.

Features:
- News classification (Fed, FOMC, CPI, NFP, PCE, Powell speech)
- Fixed cooldown windows by news type
- Volatility confirmation (ATR ratio + regime check)
- Deterministic blocking logic
- Audit-safe logging
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json
import pandas as pd
from enum import Enum


# News type classification patterns
NEWS_PATTERNS = {
    'FED_SIGNALS': {
        'patterns': [
            r'\b(fed|federal reserve)\s+(guidance|signal|hint|suggests|indicates)',
            r'\b(fed|federal reserve)\s+(official|member|governor)\s+(says|states|comments)',
            r'\b(fed|federal reserve)\s+(forward guidance|monetary policy guidance)',
        ],
        'cooldown_minutes': 90,
        'keywords': ['fed guidance', 'federal reserve guidance', 'fed signal', 'monetary policy signal']
    },
    'FOMC_DECISION': {
        'patterns': [
            r'\b(fomc|federal open market committee)\s+(decision|meeting|announcement|statement)',
            r'\b(fomc)\s+(rate|interest rate)\s+(decision|announcement)',
            r'\b(fomc)\s+(meeting|statement|minutes)',
        ],
        'cooldown_minutes': 150,
        'keywords': ['fomc decision', 'fomc meeting', 'fomc announcement', 'fomc statement']
    },
    'FOMC_SPEECH': {
        'patterns': [
            r'\b(powell|jerome powell|fed chair)\s+(speech|testimony|remarks|comments)',
            r'\b(fed chair|federal reserve chair)\s+(speech|testimony)',
            r'\b(powell)\s+(speaks|testifies|remarks)',
        ],
        'cooldown_minutes': 150,
        'keywords': ['powell speech', 'fed chair speech', 'powell testimony', 'powell remarks']
    },
    'CPI': {
        'patterns': [
            r'\b(cpi|consumer price index)\s+(report|data|release|announcement)',
            r'\b(cpi)\s+(inflation|inflation data)',
            r'\b(consumer price index)\s+(report|data)',
        ],
        'cooldown_minutes': 75,
        'keywords': ['cpi report', 'cpi data', 'consumer price index', 'cpi release']
    },
    'NFP': {
        'patterns': [
            r'\b(nfp|non.?farm payroll|non.?farm payrolls)\s+(report|data|release)',
            r'\b(non.?farm payroll)\s+(report|data)',
            r'\b(jobs report|employment report)\s+(non.?farm)',
        ],
        'cooldown_minutes': 75,
        'keywords': ['nfp report', 'non-farm payroll', 'jobs report', 'nfp data']
    },
    'PCE': {
        'patterns': [
            r'\b(pce|personal consumption expenditures)\s+(report|data|release)',
            r'\b(pce)\s+(inflation|price index)',
            r'\b(personal consumption expenditures)\s+(report|data)',
        ],
        'cooldown_minutes': 75,
        'keywords': ['pce report', 'pce data', 'personal consumption expenditures', 'pce release']
    },
}

# Impact level classification
IMPACT_LEVELS = {
    'HIGH': ['FED_SIGNALS', 'FOMC_DECISION', 'FOMC_SPEECH', 'CPI', 'NFP', 'PCE'],
    'MEDIUM': [],
    'LOW': []
}


class NewsClassification(Enum):
    """Classification of news items based on freshness"""
    LIVE_EVENT = "LIVE_EVENT"  # Fresh origin + fresh fetch
    STALE_CONTEXT = "STALE_CONTEXT"  # Old origin, fresh fetch (historical context)
    EXPIRED = "EXPIRED"  # Fetch timestamp expired
    UNVERIFIED = "UNVERIFIED"  # Cannot verify freshness


class NewsBlock:
    """
    Represents a single high-impact news event that blocks trading.
    Tracks both origin_timestamp (when event occurred) and fetch_timestamp (when retrieved).
    """
    def __init__(self, news_type: str, origin_timestamp: datetime, fetch_timestamp: datetime, 
                 source: str, headline: str, impact_level: str, classification: NewsClassification):
        self.news_type = news_type
        self.origin_timestamp = origin_timestamp  # When the news actually occurred/published
        self.fetch_timestamp = fetch_timestamp  # When the system retrieved it
        self.source = source
        self.headline = headline
        self.impact_level = impact_level
        self.classification = classification  # LIVE_EVENT, STALE_CONTEXT, EXPIRED, UNVERIFIED
        
        # Use origin_timestamp for cooldown calculation (event-based timing)
        self.timestamp = origin_timestamp  # Backward compatibility
        
        # Calculate block_until based on cooldown from origin timestamp
        cooldown_config = NEWS_PATTERNS.get(news_type, {})
        cooldown_minutes = cooldown_config.get('cooldown_minutes', 90)
        self.cooldown_minutes = cooldown_minutes
        self.block_until = origin_timestamp + timedelta(minutes=cooldown_minutes)
    
    def is_active(self, now: datetime) -> bool:
        """Check if block is still active (cooldown not expired)"""
        return now < self.block_until
    
    def minutes_remaining(self, now: datetime) -> int:
        """Get minutes remaining in cooldown"""
        if not self.is_active(now):
            return 0
        delta = self.block_until - now
        return int(delta.total_seconds() / 60)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for logging"""
        return {
            'news_type': self.news_type,
            'origin_timestamp': self.origin_timestamp.isoformat(),
            'fetch_timestamp': self.fetch_timestamp.isoformat(),
            'timestamp': self.timestamp.isoformat(),  # Backward compatibility
            'source': self.source,
            'headline': self.headline,
            'impact_level': self.impact_level,
            'classification': self.classification.value,
            'cooldown_minutes': self.cooldown_minutes,
            'block_until': self.block_until.isoformat()
        }


class HighImpactNewsBlocker:
    """
    Main module for blocking trades during high-impact news events.
    
    Implements:
    1. News classification from headlines
    2. Time-based cooldown windows
    3. Volatility confirmation (ATR ratio + regime check)
    4. Deterministic blocking logic
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        
        # News control configuration
        news_control = self.config.get('news_control', {})
        self.max_news_age_minutes = news_control.get('max_news_age_minutes', 60)
        self.high_impact_block_minutes = news_control.get('high_impact_block_minutes', 90)
        self.stale_news_policy = news_control.get('stale_news_policy', 'IGNORE')
        self.impact_relevance_window_minutes = news_control.get('impact_relevance_window_minutes', 180)
        
        # Active blocks (persisted across calls)
        self._active_blocks: List[NewsBlock] = []
        
        # Track seen events to detect stale context (headline signature -> last seen timestamp)
        self._seen_events: Dict[str, datetime] = {}  # headline_hash -> last_origin_timestamp
        
        # Compile regex patterns for efficiency
        self._compiled_patterns = {}
        for news_type, config in NEWS_PATTERNS.items():
            patterns = [re.compile(p, re.IGNORECASE) for p in config['patterns']]
            self._compiled_patterns[news_type] = patterns
    
    def classify_news(self, headline: str, source: str = 'Unknown') -> Optional[Dict]:
        """
        Classify a news headline to determine if it's high-impact.
        
        Args:
            headline: News headline text
            source: News source name
            
        Returns:
            Dict with news_type, impact_level, or None if not high-impact
        """
        headline_lower = headline.lower()
        
        # Check each news type
        for news_type, config in NEWS_PATTERNS.items():
            # Check keywords first (faster)
            keywords = config.get('keywords', [])
            if any(kw in headline_lower for kw in keywords):
                impact_level = 'HIGH' if news_type in IMPACT_LEVELS['HIGH'] else 'MEDIUM'
                return {
                    'news_type': news_type,
                    'impact_level': impact_level,
                    'source': source,
                    'headline': headline
                }
            
            # Check regex patterns
            patterns = self._compiled_patterns.get(news_type, [])
            for pattern in patterns:
                if pattern.search(headline):
                    impact_level = 'HIGH' if news_type in IMPACT_LEVELS['HIGH'] else 'MEDIUM'
                    return {
                        'news_type': news_type,
                        'impact_level': impact_level,
                        'source': source,
                        'headline': headline
                    }
        
        return None
    
    def _parse_timestamp(self, timestamp_str) -> Optional[datetime]:
        """Parse timestamp string to datetime"""
        if not timestamp_str:
            return None
        
        try:
            if isinstance(timestamp_str, str):
                if 'T' in timestamp_str:
                    if timestamp_str.endswith('Z'):
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    elif '+' in timestamp_str or timestamp_str.count('-') > 2:
                        timestamp = datetime.fromisoformat(timestamp_str)
                    else:
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', ''))
                        timestamp = timestamp.replace(tzinfo=None)
                else:
                    timestamp = datetime.fromisoformat(timestamp_str)
            elif isinstance(timestamp_str, (int, float)):
                timestamp = datetime.utcfromtimestamp(timestamp_str)
            else:
                return None
            
            if timestamp.tzinfo:
                timestamp = timestamp.replace(tzinfo=None)
            
            return timestamp
        except Exception:
            return None
    
    def _validate_and_parse_timestamps(self, item: Dict, fetch_time: datetime) -> Tuple[Optional[datetime], Optional[datetime], NewsClassification]:
        """
        Validate and parse both origin_timestamp and fetch_timestamp.
        
        Args:
            item: News item dict (may contain origin_timestamp, fetch_timestamp, published, timestamp)
            fetch_time: When this news was fetched by the system
            
        Returns:
            (origin_timestamp or None, fetch_timestamp or None, classification)
        """
        # Get origin_timestamp (when event occurred/published)
        origin_str = (item.get('origin_timestamp') or item.get('published') or 
                     item.get('timestamp') or item.get('timestamp_utc') or item.get('time'))
        origin_timestamp = self._parse_timestamp(origin_str) if origin_str else None
        
        # Get fetch_timestamp (when system retrieved it)
        fetch_str = item.get('fetch_timestamp')
        fetch_timestamp = self._parse_timestamp(fetch_str) if fetch_str else fetch_time  # Default to fetch_time if not provided
        
        # Classify based on availability and freshness
        if not origin_timestamp:
            return None, fetch_timestamp, NewsClassification.UNVERIFIED
        
        if fetch_timestamp is None:
            return origin_timestamp, None, NewsClassification.UNVERIFIED
        
        # Calculate ages
        fetch_age_minutes = (fetch_time - fetch_timestamp).total_seconds() / 60 if fetch_timestamp else float('inf')
        origin_age_minutes = (fetch_time - origin_timestamp).total_seconds() / 60 if origin_timestamp else float('inf')
        
        # Classification logic
        if fetch_age_minutes > self.max_news_age_minutes:
            # Fetch timestamp expired (cache too old)
            return origin_timestamp, fetch_timestamp, NewsClassification.EXPIRED
        
        if origin_age_minutes > self.impact_relevance_window_minutes:
            # Origin timestamp too old (event happened too long ago)
            return origin_timestamp, fetch_timestamp, NewsClassification.STALE_CONTEXT
        
        # Both timestamps are fresh
        return origin_timestamp, fetch_timestamp, NewsClassification.LIVE_EVENT
    
    def _create_event_signature(self, headline: str, news_type: str) -> str:
        """Create a signature for tracking seen events"""
        # Normalize headline (lowercase, remove extra spaces)
        normalized = ' '.join(headline.lower().split())
        # Combine with news type for uniqueness
        return f"{news_type}:{normalized[:100]}"  # Limit length
    
    def detect_high_impact_news(self, news_items: List[Dict], fetch_time: datetime = None) -> List[NewsBlock]:
        """
        Scan news items and detect high-impact events with true recency validation.
        
        Args:
            news_items: List of news dicts with 'headline', 'source', timestamps
            fetch_time: When news was fetched (defaults to now)
            
        Returns:
            List of NewsBlock objects for detected high-impact events (only LIVE_EVENT classification)
        """
        detected_blocks = []
        now = fetch_time or datetime.now()
        
        for item in news_items:
            headline = item.get('headline', '') or item.get('title', '')
            source = item.get('source', 'Unknown')
            
            # TRUE RECENCY VALIDATION: Parse both timestamps and classify
            origin_timestamp, fetch_timestamp, classification = self._validate_and_parse_timestamps(item, now)
            
            # CRITICAL: UNVERIFIED or EXPIRED news cannot block trades
            if classification in [NewsClassification.UNVERIFIED, NewsClassification.EXPIRED]:
                continue  # Skip unverifiable or expired news
            
            # Classify news type and impact
            news_classification = self.classify_news(headline, source)
            if not news_classification or news_classification['impact_level'] != 'HIGH':
                continue  # Only HIGH impact news can block
            
            news_type = news_classification['news_type']
            
            # STALE_CONTEXT PROTECTION: Check if this is a previously seen event
            event_signature = self._create_event_signature(headline, news_type)
            if classification == NewsClassification.STALE_CONTEXT:
                # Check if we've seen this event before
                if event_signature in self._seen_events:
                    last_origin = self._seen_events[event_signature]
                    # If origin timestamp matches or is older than last seen, it's stale context
                    if origin_timestamp <= last_origin:
                        # STALE_CONTEXT must never block trades
                        continue
                # Update seen events even for stale context (for tracking)
                self._seen_events[event_signature] = origin_timestamp
                # STALE_CONTEXT never blocks - skip
                continue
            
            # Only LIVE_EVENT classification can create blocks
            if classification != NewsClassification.LIVE_EVENT:
                continue
            
            # Verify both conditions for blocking:
            # 1. Fetch timestamp must be fresh (already checked in classification)
            # 2. Origin timestamp must be within blocking window
            origin_age_minutes = (now - origin_timestamp).total_seconds() / 60
            if origin_age_minutes > self.high_impact_block_minutes:
                # Origin too old for blocking window
                continue
            
            # Create block for LIVE_EVENT only
            news_block = NewsBlock(
                news_type=news_type,
                origin_timestamp=origin_timestamp,
                fetch_timestamp=fetch_timestamp or now,
                source=source,
                headline=headline,
                impact_level=news_classification['impact_level'],
                classification=classification
            )
            detected_blocks.append(news_block)
            
            # Update seen events
            self._seen_events[event_signature] = origin_timestamp
        
        return detected_blocks
    
    def update_active_blocks(self, news_items: List[Dict], fetch_time: datetime = None):
        """
        Update active blocks from latest news items with true recency validation.
        Removes expired blocks and adds new ones.
        
        Args:
            news_items: Latest news items to scan
            fetch_time: When news was fetched (defaults to now)
        """
        now = fetch_time or datetime.now()
        
        # Remove expired blocks (both cooldown expired AND origin age expired)
        self._active_blocks = [
            b for b in self._active_blocks 
            if (b.is_active(now) and 
                (now - b.origin_timestamp).total_seconds() / 60 <= self.high_impact_block_minutes and
                (now - b.fetch_timestamp).total_seconds() / 60 <= self.max_news_age_minutes and
                b.classification == NewsClassification.LIVE_EVENT)  # Only LIVE_EVENT blocks remain active
        ]
        
        # Detect new high-impact news (only LIVE_EVENT classification will be returned)
        new_blocks = self.detect_high_impact_news(news_items, fetch_time=now)
        
        # Add new blocks (avoid duplicates by checking recent timestamps)
        for new_block in new_blocks:
            # Check if we already have a similar block (same type, within 1 hour of origin)
            is_duplicate = False
            for existing in self._active_blocks:
                if (existing.news_type == new_block.news_type and
                    abs((existing.origin_timestamp - new_block.origin_timestamp).total_seconds()) < 3600):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                self._active_blocks.append(new_block)
    
    def is_blocked(self, now: datetime = None) -> Tuple[bool, Optional[NewsBlock], Optional[str]]:
        """
        Check if trading is currently blocked by high-impact news.
        
        Args:
            now: Current datetime (defaults to now)
            
        Returns:
            (is_blocked: bool, active_block: NewsBlock or None, reason: str or None)
        """
        if now is None:
            now = datetime.now()
        
        # Check active blocks
        for block in self._active_blocks:
            if block.is_active(now):
                return True, block, 'HIGH_IMPACT_NEWS'
        
        return False, None, None
    
    def check_volatility_confirmation(self, df: pd.DataFrame, timeframe: str = None) -> Tuple[bool, str]:
        """
        Check if volatility has normalized after cooldown.
        
        Trading resumes only if:
        - Cooldown elapsed (checked separately)
        - Regime is TREND or RANGE (not HIGH_VOLATILITY or CHAOTIC)
        - ATR ratio <= 1.5
        
        Args:
            df: DataFrame with ATR column
            timeframe: Optional timeframe for threshold lookup
            
        Returns:
            (can_trade: bool, reason: str)
        """
        if df is None or len(df) < 50:
            return False, "Insufficient data for volatility check"
        
        try:
            latest = df.iloc[-1]
            
            # Check ATR ratio
            if 'ATR' in df.columns and pd.notna(latest['ATR']):
                atr = float(latest['ATR'])
                recent_atr = df['ATR'].iloc[-50:].dropna()
                if len(recent_atr) > 10:
                    avg_atr = float(recent_atr.mean())
                    atr_ratio = atr / avg_atr if avg_atr > 0 else 1.0
                else:
                    atr_ratio = 1.0
            else:
                atr_ratio = 1.0
            
            # ATR ratio check (must be <= 1.5)
            if atr_ratio > 1.5:
                return False, f"ATR ratio {atr_ratio:.2f} > 1.5 (volatility not normalized)"
            
            # Note: Regime check is done separately in the calling code
            # This function only checks ATR
            
            return True, "Volatility normalized"
            
        except Exception as e:
            return False, f"Volatility check error: {str(e)}"
    
    def get_block_status(self, now: datetime = None) -> Dict:
        """
        Get current block status for UI/logging with TTL validation.
        
        Returns:
            Dict with block status, active block info, and standardized wording
        """
        if now is None:
            now = datetime.now()
        
        is_blocked, active_block, reason = self.is_blocked(now)
        
        # CRITICAL: Double-check TTL even for active blocks (both timestamps must be fresh)
        if is_blocked and active_block:
            origin_age_minutes = (now - active_block.origin_timestamp).total_seconds() / 60
            fetch_age_minutes = (now - active_block.fetch_timestamp).total_seconds() / 60
            
            # Block expires if origin age > blocking window OR fetch age > TTL OR not LIVE_EVENT
            if (origin_age_minutes > self.high_impact_block_minutes or
                fetch_age_minutes > self.max_news_age_minutes or
                active_block.classification != NewsClassification.LIVE_EVENT):
                # Block expired - auto-unblock
                is_blocked = False
                active_block = None
                reason = None
        
        if not is_blocked:
            return {
                'is_blocked': False,
                'can_trade': True,
                'reason': None,
                'details': None,
                'ui_wording': None,
                'event_age_minutes': None,
                'block_expires_in_minutes': None
            }
        
        # Format standardized UI wording
        minutes_remaining = active_block.minutes_remaining(now)
        event_age_minutes = (now - active_block.origin_timestamp).total_seconds() / 60
        fetch_age_minutes = (now - active_block.fetch_timestamp).total_seconds() / 60
        
        # Format news type for display
        news_type_display = active_block.news_type.replace('_', ' ').title()
        if 'Fed' in news_type_display or 'Fomc' in news_type_display:
            news_type_display = news_type_display.replace('Fed', 'Fed').replace('Fomc', 'FOMC')
        
        details = f"{news_type_display} – cooldown active (expires in {minutes_remaining} min)"
        
        ui_wording = {
            'decision': 'NO_TRADE',
            'risk_allocation': '0%',
            'capital_at_risk': '$0.00',
            'reason': 'HIGH_IMPACT_NEWS',
            'details': details
        }
        
        return {
            'is_blocked': True,
            'can_trade': False,
            'reason': reason,
            'active_block': active_block.to_dict(),
            'minutes_remaining': minutes_remaining,
            'cooldown_minutes': active_block.cooldown_minutes,
            'news_event': active_block.news_type,
            'impact_level': active_block.impact_level,
            'headline': active_block.headline,
            'source': active_block.source,
            'block_until': active_block.block_until.isoformat(),
            'origin_timestamp': active_block.origin_timestamp.isoformat(),
            'fetch_timestamp': active_block.fetch_timestamp.isoformat(),
            'event_age_minutes': round(event_age_minutes, 1),
            'fetch_age_minutes': round(fetch_age_minutes, 1),
            'cache_age_minutes': round(fetch_age_minutes, 1),
            'classification': active_block.classification.value,
            'block_expires_in_minutes': minutes_remaining,
            'details': details,
            'ui_wording': ui_wording
        }
    
    def save_state(self, filepath: str):
        """Save active blocks to file for persistence"""
        state = {
            'saved_at': datetime.now().isoformat(),
            'active_blocks': [b.to_dict() for b in self._active_blocks]
        }
        
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w') as f:
            json.dump(state, f, indent=2, default=str)
    
    def load_state(self, filepath: str):
        """Load active blocks from file"""
        path = Path(filepath)
        if not path.exists():
            return
        
        try:
            with open(path, 'r') as f:
                state = json.load(f)
            
            self._active_blocks = []
            for block_data in state.get('active_blocks', []):
                news_block = NewsBlock(
                    news_type=block_data['news_type'],
                    timestamp=datetime.fromisoformat(block_data['timestamp']),
                    source=block_data['source'],
                    headline=block_data['headline'],
                    impact_level=block_data['impact_level']
                )
                # Restore block_until (should match calculated value)
                self._active_blocks.append(news_block)
        except Exception as e:
            print(f"  ⚠️ Failed to load news blocker state: {e}")


# Singleton instance
_news_blocker_instance = None

def get_news_blocker(config: Dict = None) -> HighImpactNewsBlocker:
    """Get or create singleton NewsBlocker"""
    global _news_blocker_instance
    if _news_blocker_instance is None or config:
        _news_blocker_instance = HighImpactNewsBlocker(config)
        # Try to load persisted state
        state_file = Path(__file__).parent / 'news_blocker_state.json'
        if state_file.exists():
            _news_blocker_instance.load_state(str(state_file))
    return _news_blocker_instance


if __name__ == "__main__":
    # Test the news blocker
    print("=" * 60)
    print("High-Impact News Blocker Test")
    print("=" * 60)
    
    blocker = HighImpactNewsBlocker()
    
    # Test news items
    test_news = [
        {
            'headline': 'FOMC Announces Interest Rate Decision',
            'source': 'Reuters',
            'published': datetime.now().isoformat()
        },
        {
            'headline': 'CPI Report Shows Higher Inflation',
            'source': 'Bloomberg',
            'published': (datetime.now() - timedelta(minutes=30)).isoformat()
        },
        {
            'headline': 'Fed Chair Powell Speech on Monetary Policy',
            'source': 'CNBC',
            'published': (datetime.now() - timedelta(hours=1)).isoformat()
        },
        {
            'headline': 'Gold Prices Rise on Safe Haven Demand',
            'source': 'MarketWatch',
            'published': datetime.now().isoformat()
        }
    ]
    
    print("\n📰 Testing news classification...")
    for item in test_news:
        classification = blocker.classify_news(item['headline'], item['source'])
        if classification:
            print(f"  ✓ HIGH IMPACT: {classification['news_type']} - {item['headline'][:50]}")
        else:
            print(f"  ⚪ Not high-impact: {item['headline'][:50]}")
    
    print("\n🛡️ Testing block detection...")
    blocker.update_active_blocks(test_news)
    status = blocker.get_block_status()
    
    if status['is_blocked']:
        print(f"  ⛔ BLOCKED: {status['details']}")
        print(f"     News Type: {status['news_event']}")
        print(f"     Minutes Remaining: {status['minutes_remaining']}")
        print(f"     UI Wording: {status['ui_wording']}")
    else:
        print("  ✅ Not blocked")


