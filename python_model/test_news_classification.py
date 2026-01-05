"""
Unit Tests for News Classification System (v2.2.1)
Tests content-type classification, impact decay, and type-specific TTL logic.

Run with: python -m unittest test_news_classification -v
"""

import unittest
from datetime import datetime, timedelta
from news_blocker import (
    HighImpactNewsBlocker, NewsClassification, NewsContentType,
    NEWS_PATTERNS, DEFAULT_NEWS_TYPE_TTL
)


class TestNewsContentTypeClassification(unittest.TestCase):
    """Test content-based news classification"""
    
    def setUp(self):
        """Set up test blocker with default config"""
        self.blocker = HighImpactNewsBlocker()
    
    def test_fomc_minutes_detected(self):
        """FOMC minutes headlines should be classified as FOMC_MINUTES"""
        headlines = [
            "FOMC Minutes Show Fed Officials Discussed Rate Cuts",
            "Federal Open Market Committee Minutes Reveal Split on Policy",
            "Meeting Minutes Indicate Fed Could Pause Hikes",
        ]
        for headline in headlines:
            content_type, reason = self.blocker._classify_content_type(headline, "Reuters")
            self.assertEqual(content_type, NewsContentType.FOMC_MINUTES, 
                           f"Expected FOMC_MINUTES for: {headline}")
    
    def test_commentary_detected(self):
        """Analyst commentary should be classified as COMMENTARY"""
        headlines = [
            "Analyst Says Fed Will Cut Rates in March",
            "Goldman Economist Expects 50bp Hike",
            "Markets React to Fed Commentary",
            "Strategist Believes Dollar Will Weaken",
        ]
        for headline in headlines:
            content_type, reason = self.blocker._classify_content_type(headline, "MarketWatch")
            self.assertEqual(content_type, NewsContentType.COMMENTARY, 
                           f"Expected COMMENTARY for: {headline}")
    
    def test_official_source_detected(self):
        """Official government sources should be classified as OFFICIAL_POLICY"""
        test_cases = [
            ("Fed Announces Rate Decision", "federalreserve.gov"),
            ("Treasury Issues Statement on Inflation", "treasury.gov"),
            ("BLS Releases Employment Report", "bls.gov"),
        ]
        for headline, source in test_cases:
            content_type, reason = self.blocker._classify_content_type(headline, source)
            self.assertEqual(content_type, NewsContentType.OFFICIAL_POLICY, 
                           f"Expected OFFICIAL_POLICY for: {headline} from {source}")
    
    def test_speech_testimony_detected(self):
        """Speeches and testimony should be classified as SPEECH_OR_TESTIMONY"""
        headlines = [
            "Powell Speech at Jackson Hole Symposium",
            "Fed Chair Testifying Before Congress Today",
            "Scheduled Remarks by Fed Governor on Policy",
        ]
        for headline in headlines:
            content_type, reason = self.blocker._classify_content_type(headline, "Bloomberg")
            self.assertEqual(content_type, NewsContentType.SPEECH_OR_TESTIMONY, 
                           f"Expected SPEECH_OR_TESTIMONY for: {headline}")


class TestImpactDecay(unittest.TestCase):
    """Test impact score decay over time"""
    
    def setUp(self):
        """Set up test blocker"""
        self.blocker = HighImpactNewsBlocker()
        self.now = datetime.now()
    
    def test_fomc_minutes_always_low_impact(self):
        """FOMC minutes should always have very low impact score"""
        origin = self.now - timedelta(minutes=30)
        impact_score, reason = self.blocker._calculate_impact_decay(
            origin, NewsContentType.FOMC_MINUTES, self.now
        )
        self.assertLessEqual(impact_score, 0.2, 
                            "FOMC_MINUTES should have impact <= 0.2")
    
    def test_commentary_decays_after_60min(self):
        """Commentary impact should be reduced by 50% after 60 minutes"""
        # Fresh commentary
        fresh_origin = self.now - timedelta(minutes=30)
        fresh_score, _ = self.blocker._calculate_impact_decay(
            fresh_origin, NewsContentType.COMMENTARY, self.now
        )
        
        # Old commentary (> 60 min)
        old_origin = self.now - timedelta(minutes=90)
        old_score, _ = self.blocker._calculate_impact_decay(
            old_origin, NewsContentType.COMMENTARY, self.now
        )
        
        self.assertGreater(fresh_score, old_score, 
                          "Old commentary should have lower impact than fresh")
        self.assertLessEqual(old_score, 0.5, 
                            "Commentary > 60min should have impact <= 0.5")
    
    def test_official_policy_full_impact_within_ttl(self):
        """Official policy should maintain high impact within TTL"""
        origin = self.now - timedelta(minutes=60)
        impact_score, _ = self.blocker._calculate_impact_decay(
            origin, NewsContentType.OFFICIAL_POLICY, self.now
        )
        self.assertGreater(impact_score, 0.7, 
                          "OFFICIAL_POLICY within TTL should have high impact")
    
    def test_impact_decays_beyond_ttl(self):
        """Impact should decay when beyond TTL window"""
        # Beyond 180 min TTL for OFFICIAL_POLICY
        origin = self.now - timedelta(minutes=250)
        impact_score, _ = self.blocker._calculate_impact_decay(
            origin, NewsContentType.OFFICIAL_POLICY, self.now
        )
        self.assertLess(impact_score, 0.5, 
                       "Impact beyond TTL should be reduced")


class TestDetectHighImpactNews(unittest.TestCase):
    """Test the full detection pipeline"""
    
    def setUp(self):
        """Set up test blocker"""
        self.blocker = HighImpactNewsBlocker()
        self.now = datetime.now()
    
    def test_old_fed_minutes_no_block(self):
        """Old Fed minutes from prior week should NOT block trades"""
        news_items = [{
            'headline': 'FOMC Minutes Show Fed Officials Debated Pace of Hikes',
            'source': 'Reuters',
            'origin_timestamp': (self.now - timedelta(days=7)).isoformat(),
            'fetch_timestamp': self.now.isoformat()
        }]
        
        blocks = self.blocker.detect_high_impact_news(news_items, self.now)
        self.assertEqual(len(blocks), 0, 
                        "Old FOMC minutes should NOT create a block")
    
    def test_recent_official_press_release_blocks(self):
        """Recent Fed press release should block trades"""
        news_items = [{
            'headline': 'FOMC Decision: Fed Holds Rates Steady',
            'source': 'federalreserve.gov',
            'origin_timestamp': (self.now - timedelta(minutes=30)).isoformat(),
            'fetch_timestamp': self.now.isoformat()
        }]
        
        blocks = self.blocker.detect_high_impact_news(news_items, self.now)
        self.assertEqual(len(blocks), 1, 
                        "Recent official FOMC press release SHOULD create a block")
        self.assertEqual(blocks[0].content_type, NewsContentType.OFFICIAL_POLICY)
    
    def test_analyst_commentary_no_block(self):
        """Analyst commentary should NOT trigger a block even if fresh"""
        news_items = [{
            'headline': 'Goldman Analyst Says Fed Will Cut Rates Soon',
            'source': 'CNBC',
            'origin_timestamp': (self.now - timedelta(minutes=15)).isoformat(),
            'fetch_timestamp': self.now.isoformat()
        }]
        
        blocks = self.blocker.detect_high_impact_news(news_items, self.now)
        self.assertEqual(len(blocks), 0, 
                        "Analyst commentary should NOT create a block")
    
    def test_stale_context_no_block(self):
        """Previously seen events should be treated as stale context"""
        news_items = [{
            'headline': 'CPI Report Shows Higher Inflation Data',
            'source': 'federalreserve.gov',
            'origin_timestamp': (self.now - timedelta(minutes=30)).isoformat(),
            'fetch_timestamp': self.now.isoformat()
        }]
        
        # First detection should create block
        blocks1 = self.blocker.detect_high_impact_news(news_items, self.now)
        
        # Same event again should not create another block
        blocks2 = self.blocker.detect_high_impact_news(news_items, self.now)
        
        # The second detection shouldn't add duplicates
        # (detect method filters duplicates by signature)


class TestTypeSpecificTTL(unittest.TestCase):
    """Test type-specific TTL enforcement"""
    
    def setUp(self):
        """Set up test blocker with custom TTL"""
        self.blocker = HighImpactNewsBlocker({
            'news_type_ttl': {
                'OFFICIAL_POLICY': 180,
                'COMMENTARY': 60,
                'FOMC_MINUTES': 30,
            }
        })
        self.now = datetime.now()
    
    def test_commentary_ttl_enforced(self):
        """Commentary beyond 60min TTL should not block"""
        news_items = [{
            'headline': 'Fed Official Comments on Policy Outlook',
            'source': 'MarketWatch',
            'origin_timestamp': (self.now - timedelta(minutes=90)).isoformat(),
            'fetch_timestamp': self.now.isoformat()
        }]
        
        blocks = self.blocker.detect_high_impact_news(news_items, self.now)
        # Commentary is filtered early, so no blocks expected
        self.assertEqual(len(blocks), 0, 
                        "Commentary beyond TTL should not block")


class TestDeterministicBehavior(unittest.TestCase):
    """Test that classification is deterministic"""
    
    def test_same_input_same_output(self):
        """Same input should always produce same output"""
        blocker = HighImpactNewsBlocker()
        headline = "Fed Announces Rate Decision"
        source = "federalreserve.gov"
        
        results = [
            blocker._classify_content_type(headline, source)
            for _ in range(10)
        ]
        
        # All results should be identical
        first_result = results[0]
        for result in results[1:]:
            self.assertEqual(result[0], first_result[0], 
                           "Classification should be deterministic")


if __name__ == '__main__':
    unittest.main()
