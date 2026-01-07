"""
Sentiment Analyzer Module - News Sentiment for Gold Trading
Processes news headlines and computes sentiment scores.

Features:
- Rule-based sentiment analysis (no external API needed)
- Gold-specific sentiment lexicon
- Aggregated sentiment scoring
- High-impact event detection
"""

import re
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from collections import defaultdict


# Gold-specific sentiment lexicon
# Positive for Gold price (bullish)
GOLD_BULLISH_WORDS = {
    # Direct bullish terms
    'rally': 2.0, 'surge': 2.0, 'soar': 2.0, 'jump': 1.5, 'climb': 1.5,
    'gain': 1.0, 'rise': 1.0, 'higher': 1.0, 'advance': 1.0, 'up': 0.5,
    'bullish': 2.0, 'bull': 1.5, 'buy': 1.0, 'buying': 1.0, 'demand': 1.5,
    'support': 1.0, 'breakout': 1.5, 'momentum': 1.0,
    
    # Macro factors bullish for Gold
    'inflation': 1.5, 'inflationary': 1.5, 'dovish': 2.0, 'rate cut': 2.5,
    'stimulus': 2.0, 'easing': 1.5, 'quantitative easing': 2.0, 'qe': 2.0,
    'safe haven': 2.0, 'haven': 1.5, 'uncertainty': 1.0, 'risk off': 1.5,
    'geopolitical': 1.0, 'tension': 1.0, 'conflict': 1.0, 'war': 1.5,
    'crisis': 1.5, 'recession': 1.0, 'slowdown': 1.0,
    'weak dollar': 2.0, 'dollar weakness': 2.0, 'dxy down': 1.5,
    'central bank buying': 2.0, 'reserve': 1.0,
    
    # Supply factors
    'shortage': 1.5, 'supply constraint': 1.5, 'mining disruption': 1.5,
}

# Negative for Gold price (bearish)
GOLD_BEARISH_WORDS = {
    # Direct bearish terms
    'fall': -1.5, 'drop': -1.5, 'decline': -1.5, 'slide': -1.5, 'plunge': -2.0,
    'crash': -2.5, 'tumble': -2.0, 'slump': -2.0, 'sink': -1.5,
    'loss': -1.0, 'lower': -1.0, 'down': -0.5, 'weak': -1.0,
    'bearish': -2.0, 'bear': -1.5, 'sell': -1.0, 'selling': -1.0,
    'resistance': -0.5, 'breakdown': -1.5,
    
    # Macro factors bearish for Gold
    'hawkish': -2.0, 'rate hike': -2.5, 'rate increase': -2.0, 'tightening': -1.5,
    'strong dollar': -2.0, 'dollar strength': -2.0, 'dxy up': -1.5,
    'risk on': -1.0, 'equity rally': -1.0, 'stock surge': -1.0,
    'deflation': -1.5, 'deflationary': -1.5,
    'yield rise': -1.5, 'treasury yield': -1.0, 'real yield': -1.0,
    
    # Supply factors
    'oversupply': -1.5, 'surplus': -1.0,
}

# Neutral/noise words to ignore
NOISE_WORDS = {
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
    'could', 'should', 'may', 'might', 'must', 'shall',
    'and', 'or', 'but', 'if', 'then', 'else', 'when', 'where',
    'who', 'what', 'which', 'this', 'that', 'these', 'those',
    'for', 'to', 'from', 'with', 'by', 'at', 'in', 'on', 'of',
}

# XAUUSD High-impact event patterns ONLY
# These patterns DIRECTLY and SIGNIFICANTLY move Gold/USD price
# Removed: ecb, boe, boj (don't directly affect XAUUSD)
HIGH_IMPACT_PATTERNS = [
    # US Fed - THE most important for XAUUSD
    r'\b(fed|fomc|federal reserve)\s+(meeting|decision|announce|rate|statement)',
    r'\b(fed|fomc)\s+(hike|cut|pause|pivot)',
    r'\bpowell\s+(speaks?|speech|testimony)',
    # US Interest rates
    r'\b(rate\s+)(hike|cut|decision)\s+(announce|surprise|shock)',
    # US Economic data (major USD movers)
    r'\b(cpi|inflation)\s+(report|data|surprise|shock)',
    r'\b(non.?farm|nfp|payroll)\s+(report|data|surprise|miss|beat)',
    r'\b(us\s+)?gdp\s+(report|data|surprise|shock)',
    r'\b(us\s+)?unemployment\s+rate',
    # Dollar-specific shocks
    r'\bdollar\s+(crash|surge|plunge|collapse)',
    r'\bdxy\s+(crash|surge|plunge)',
    # Gold-specific events
    r'\bgold\s+(crash|surge|plunge|rally|collapse)',
    r'\bcentral\s+bank\s+gold\s+(buying|purchase|reserve)',
    # Geopolitical (safe-haven triggers)
    r'\b(war|invasion|military strike|nuclear)',
    # Market crisis (flight to Gold)
    r'\b(emergency|crisis|crash|collapse)\s+(rate|market|bank)',
]

# v2.2.1: Commentary patterns to EXCLUDE from high impact
# These indicate market interpretation, not official announcements
COMMENTARY_EXCLUSION_PATTERNS = [
    r'\b(signals?|hints?)\s+(potential|possible|likely)',
    r'\bamid\s+(cooling|rising|slowing|weakening)',
    r'\b(analyst|economist|strategist)\s+(says|expects|believes)',
    r'\b(could|may|might)\s+(signal|pause|cut|hike)',
    r'\bpotential\s+(rate|pause|cut|hike)',
]


class SentimentAnalyzer:
    """
    Analyzes sentiment of financial news for Gold trading.
    Uses a rule-based approach with Gold-specific lexicon.
    """
    
    def __init__(self):
        self.bullish_lexicon = GOLD_BULLISH_WORDS
        self.bearish_lexicon = GOLD_BEARISH_WORDS
        self.noise_words = NOISE_WORDS
        self.high_impact_patterns = [re.compile(p, re.IGNORECASE) for p in HIGH_IMPACT_PATTERNS]
        # v2.2.1: Add commentary exclusion patterns
        self.commentary_exclusion_patterns = [re.compile(p, re.IGNORECASE) for p in COMMENTARY_EXCLUSION_PATTERNS]
    
    def _preprocess(self, text: str) -> List[str]:
        """
        Preprocess text for analysis.
        - Lowercase
        - Remove special characters
        - Tokenize
        - Remove noise words
        """
        # Lowercase
        text = text.lower()
        
        # Keep important punctuation patterns first
        text = text.replace("rate cut", "rate_cut")
        text = text.replace("rate hike", "rate_hike")
        text = text.replace("safe haven", "safe_haven")
        text = text.replace("risk off", "risk_off")
        text = text.replace("risk on", "risk_on")
        text = text.replace("central bank", "central_bank")
        text = text.replace("strong dollar", "strong_dollar")
        text = text.replace("weak dollar", "weak_dollar")
        
        # Remove special chars but keep underscores
        text = re.sub(r'[^\w\s_]', ' ', text)
        
        # Tokenize
        tokens = text.split()
        
        # Filter noise
        tokens = [t for t in tokens if t not in self.noise_words and len(t) > 1]
        
        # Restore spaces in compound terms
        tokens = [t.replace('_', ' ') for t in tokens]
        
        return tokens
    
    def _score_text(self, text: str) -> float:
        """
        Score a single piece of text.
        Returns score between -1.0 (very bearish) and 1.0 (very bullish).
        """
        text_lower = text.lower()
        total_score = 0.0
        match_count = 0
        
        # Check bullish lexicon
        for term, score in self.bullish_lexicon.items():
            if term in text_lower:
                total_score += score
                match_count += 1
        
        # Check bearish lexicon
        for term, score in self.bearish_lexicon.items():
            if term in text_lower:
                total_score += score  # Note: bearish scores are already negative
                match_count += 1
        
        # Normalize to -1 to 1 range
        if match_count == 0:
            return 0.0
        
        # Average score, clamped to [-1, 1]
        avg_score = total_score / max(match_count, 1)
        return max(-1.0, min(1.0, avg_score / 2.0))  # Divide by 2 to normalize
    
    def _is_high_impact(self, text: str) -> bool:
        """
        Check if text matches high-impact event patterns.
        v2.2.1: Excludes commentary/market interpretation language.
        """
        # Check for commentary exclusion patterns first
        for pattern in self.commentary_exclusion_patterns:
            if pattern.search(text):
                return False  # Commentary is NOT high impact
        
        # Now check for actual high impact patterns
        for pattern in self.high_impact_patterns:
            if pattern.search(text):
                return True
        return False
    
    def analyze_headline(self, headline: str, summary: str = "") -> Dict:
        """
        Analyze a single news headline with optional summary.
        
        Returns:
            {
                'headline': str,
                'sentiment_score': float (-1 to 1),
                'sentiment_label': str (BULLISH/NEUTRAL/BEARISH),
                'is_high_impact': bool,
                'confidence': float (0 to 1)
            }
        """
        combined_text = f"{headline} {summary}"
        
        # Score the text
        score = self._score_text(combined_text)
        
        # Determine label
        if score > 0.15:
            label = "BULLISH"
        elif score < -0.15:
            label = "BEARISH"
        else:
            label = "NEUTRAL"
        
        # Check high impact
        is_high_impact = self._is_high_impact(combined_text)
        
        # Confidence based on number of matches
        tokens = self._preprocess(combined_text)
        matches = sum(1 for t in tokens if t in self.bullish_lexicon or t in self.bearish_lexicon)
        confidence = min(1.0, matches / 5.0)  # Max confidence at 5+ matches
        
        return {
            'headline': headline,
            'sentiment_score': round(score, 3),
            'sentiment_label': label,
            'is_high_impact': is_high_impact,
            'confidence': round(confidence, 2)
        }
    
    def analyze_news_batch(self, news_items: List[Dict]) -> List[Dict]:
        """
        Analyze a batch of news items.
        
        Args:
            news_items: List of dicts with 'headline' and optional 'summary'
            
        Returns:
            List of analysis results
        """
        results = []
        
        for item in news_items:
            headline = item.get('headline', '')
            summary = item.get('summary', '')
            
            analysis = self.analyze_headline(headline, summary)
            
            # Merge with original item
            result = {
                **item,
                'sentiment_score': analysis['sentiment_score'],
                'sentiment_label': analysis['sentiment_label'],
                'is_high_impact': item.get('is_high_impact', False) or analysis['is_high_impact'],
                'sentiment_confidence': analysis['confidence']
            }
            
            results.append(result)
        
        return results
    
    def aggregate_sentiment(self, news_items: List[Dict], 
                           hours_lookback: int = 4,
                           weight_by_recency: bool = True) -> Dict:
        """
        Aggregate sentiment across multiple news items.
        
        Args:
            news_items: List of analyzed news items
            hours_lookback: Only consider news from last N hours
            weight_by_recency: Give more weight to recent news
            
        Returns:
            {
                'aggregate_score': float,
                'aggregate_label': str,
                'bullish_count': int,
                'bearish_count': int,
                'neutral_count': int,
                'has_high_impact': bool,
                'high_impact_headlines': List[str],
                'sample_size': int
            }
        """
        cutoff = datetime.now() - timedelta(hours=hours_lookback)
        
        # Filter by time
        recent_items = []
        for item in news_items:
            try:
                pub_time = item.get('published', '')
                if isinstance(pub_time, str):
                    pub_time = datetime.fromisoformat(pub_time.replace('Z', '+00:00'))
                if pub_time.replace(tzinfo=None) > cutoff:
                    recent_items.append(item)
            except:
                recent_items.append(item)  # Include if can't parse time
        
        if not recent_items:
            return {
                'aggregate_score': 0.0,
                'aggregate_label': 'NEUTRAL',
                'bullish_count': 0,
                'bearish_count': 0,
                'neutral_count': 0,
                'has_high_impact': False,
                'high_impact_headlines': [],
                'sample_size': 0
            }
        
        # Calculate weighted scores
        total_weight = 0.0
        weighted_sum = 0.0
        bullish = 0
        bearish = 0
        neutral = 0
        high_impact_headlines = []
        
        now = datetime.now()
        
        for item in recent_items:
            score = item.get('sentiment_score', 0.0)
            
            # Weight by recency
            if weight_by_recency:
                try:
                    pub_time = item.get('published', '')
                    if isinstance(pub_time, str):
                        pub_time = datetime.fromisoformat(pub_time.replace('Z', '+00:00'))
                    hours_ago = (now - pub_time.replace(tzinfo=None)).total_seconds() / 3600
                    weight = max(0.1, 1.0 - (hours_ago / hours_lookback))
                except:
                    weight = 0.5
            else:
                weight = 1.0
            
            weighted_sum += score * weight
            total_weight += weight
            
            # Count by label
            label = item.get('sentiment_label', 'NEUTRAL')
            if label == 'BULLISH':
                bullish += 1
            elif label == 'BEARISH':
                bearish += 1
            else:
                neutral += 1
            
            # Track high impact
            if item.get('is_high_impact', False):
                high_impact_headlines.append(item.get('headline', ''))
        
        # Calculate aggregate score
        aggregate_score = weighted_sum / total_weight if total_weight > 0 else 0.0
        
        # Determine label
        if aggregate_score > 0.1:
            aggregate_label = 'BULLISH'
        elif aggregate_score < -0.1:
            aggregate_label = 'BEARISH'
        else:
            aggregate_label = 'NEUTRAL'
        
        return {
            'aggregate_score': round(aggregate_score, 3),
            'aggregate_label': aggregate_label,
            'bullish_count': bullish,
            'bearish_count': bearish,
            'neutral_count': neutral,
            'has_high_impact': len(high_impact_headlines) > 0,
            'high_impact_headlines': high_impact_headlines,
            'sample_size': len(recent_items)
        }
    
    def get_sentiment_features(self, news_items: List[Dict], 
                               short_term_hours: int = 2,
                               long_term_hours: int = 8) -> Dict:
        """
        Extract sentiment features for ML model integration.
        
        Returns dict suitable for adding to feature set:
            {
                'news_sentiment_short': float,
                'news_sentiment_long': float,
                'news_high_impact': int (0 or 1),
                'news_bullish_ratio': float,
                'news_volume': int
            }
        """
        short_term = self.aggregate_sentiment(news_items, hours_lookback=short_term_hours)
        long_term = self.aggregate_sentiment(news_items, hours_lookback=long_term_hours)
        
        total = short_term['bullish_count'] + short_term['bearish_count'] + short_term['neutral_count']
        bullish_ratio = short_term['bullish_count'] / total if total > 0 else 0.5
        
        return {
            'news_sentiment_short': short_term['aggregate_score'],
            'news_sentiment_long': long_term['aggregate_score'],
            'news_high_impact': 1 if short_term['has_high_impact'] else 0,
            'news_bullish_ratio': round(bullish_ratio, 2),
            'news_volume': total
        }


# Singleton instance
_sentiment_analyzer = None

def get_sentiment_analyzer() -> SentimentAnalyzer:
    """Get or create singleton SentimentAnalyzer"""
    global _sentiment_analyzer
    if _sentiment_analyzer is None:
        _sentiment_analyzer = SentimentAnalyzer()
    return _sentiment_analyzer


if __name__ == "__main__":
    # Test the sentiment analyzer
    print("=" * 50)
    print("Sentiment Analyzer Test")
    print("=" * 50)
    
    analyzer = SentimentAnalyzer()
    
    # Test headlines
    test_headlines = [
        "Gold prices surge as Fed signals rate cut",
        "Dollar strengthens, gold under pressure",
        "Central banks continue gold buying spree",
        "Gold steady ahead of inflation data",
        "Geopolitical tensions boost safe haven demand",
        "Treasury yields rise, gold retreats",
        "Gold crashes 5% on hawkish Fed surprise",
    ]
    
    print("\nAnalyzing headlines:")
    for headline in test_headlines:
        result = analyzer.analyze_headline(headline)
        print(f"\n📰 {headline}")
        print(f"   Score: {result['sentiment_score']:+.2f} ({result['sentiment_label']})")
        print(f"   High Impact: {result['is_high_impact']}")
    
    # Test aggregation
    news_items = [{'headline': h, 'published': datetime.now().isoformat()} 
                  for h in test_headlines]
    analyzed = analyzer.analyze_news_batch(news_items)
    agg = analyzer.aggregate_sentiment(analyzed, hours_lookback=24)
    
    print(f"\n\n📊 Aggregate Sentiment:")
    print(f"   Score: {agg['aggregate_score']:+.2f} ({agg['aggregate_label']})")
    print(f"   Bullish: {agg['bullish_count']} | Bearish: {agg['bearish_count']} | Neutral: {agg['neutral_count']}")
    print(f"   High Impact: {agg['has_high_impact']}")








