"""
Economic Calendar Module - High-Impact Event Tracking
Tracks scheduled economic events that affect Gold prices.

Features:
- Known high-impact event schedules
- Event impact assessment
- Trading blackout detection
- Calendar-based risk adjustment
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import requests


# High-impact economic events with typical Gold correlation
# Impact: HIGH (major price moves), MEDIUM (moderate), LOW (minor)
HIGH_IMPACT_EVENTS = {
    # US Federal Reserve
    'FOMC_DECISION': {
        'name': 'FOMC Interest Rate Decision',
        'impact': 'HIGH',
        'gold_correlation': 'INVERSE',  # Rate hike = bearish, cut = bullish
        'typical_volatility': 3.0,  # 3x normal ATR
        'blackout_hours_before': 2,
        'blackout_hours_after': 1
    },
    'FOMC_MINUTES': {
        'name': 'FOMC Meeting Minutes',
        'impact': 'HIGH',
        'gold_correlation': 'VARIABLE',
        'typical_volatility': 2.0,
        'blackout_hours_before': 1,
        'blackout_hours_after': 0.5
    },
    'FED_CHAIR_SPEECH': {
        'name': 'Fed Chair Speech',
        'impact': 'HIGH',
        'gold_correlation': 'VARIABLE',
        'typical_volatility': 2.0,
        'blackout_hours_before': 1,
        'blackout_hours_after': 0.5
    },
    
    # US Economic Data
    'US_CPI': {
        'name': 'US Consumer Price Index (CPI)',
        'impact': 'HIGH',
        'gold_correlation': 'POSITIVE',  # High inflation = bullish
        'typical_volatility': 2.5,
        'blackout_hours_before': 1,
        'blackout_hours_after': 0.5
    },
    'US_NFP': {
        'name': 'US Non-Farm Payrolls',
        'impact': 'HIGH',
        'gold_correlation': 'INVERSE',  # Strong jobs = bearish
        'typical_volatility': 2.5,
        'blackout_hours_before': 1,
        'blackout_hours_after': 0.5
    },
    'US_GDP': {
        'name': 'US GDP Report',
        'impact': 'MEDIUM',
        'gold_correlation': 'INVERSE',
        'typical_volatility': 1.5,
        'blackout_hours_before': 0.5,
        'blackout_hours_after': 0.25
    },
    'US_UNEMPLOYMENT': {
        'name': 'US Unemployment Rate',
        'impact': 'MEDIUM',
        'gold_correlation': 'POSITIVE',  # High unemployment = bullish
        'typical_volatility': 1.5,
        'blackout_hours_before': 0.5,
        'blackout_hours_after': 0.25
    },
    'US_RETAIL_SALES': {
        'name': 'US Retail Sales',
        'impact': 'MEDIUM',
        'gold_correlation': 'INVERSE',
        'typical_volatility': 1.5,
        'blackout_hours_before': 0.5,
        'blackout_hours_after': 0.25
    },
    
    # Other Central Banks
    'ECB_DECISION': {
        'name': 'ECB Interest Rate Decision',
        'impact': 'MEDIUM',
        'gold_correlation': 'VARIABLE',
        'typical_volatility': 1.5,
        'blackout_hours_before': 1,
        'blackout_hours_after': 0.5
    },
    'BOE_DECISION': {
        'name': 'Bank of England Rate Decision',
        'impact': 'MEDIUM',
        'gold_correlation': 'VARIABLE',
        'typical_volatility': 1.5,
        'blackout_hours_before': 1,
        'blackout_hours_after': 0.5
    },
    
    # Geopolitical
    'GEOPOLITICAL_CRISIS': {
        'name': 'Geopolitical Event',
        'impact': 'HIGH',
        'gold_correlation': 'POSITIVE',  # Crisis = bullish (safe haven)
        'typical_volatility': 3.0,
        'blackout_hours_before': 0,
        'blackout_hours_after': 2
    }
}


class EconomicCalendar:
    """
    Manages economic calendar and high-impact event detection.
    """
    
    def __init__(self, cache_dir: str = None):
        self.cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / 'cache' / 'calendar'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.events_file = self.cache_dir / 'scheduled_events.json'
        self.event_definitions = HIGH_IMPACT_EVENTS
        
        # Load scheduled events
        self._scheduled_events = self._load_scheduled_events()
    
    def _load_scheduled_events(self) -> List[Dict]:
        """Load scheduled events from cache"""
        if self.events_file.exists():
            try:
                with open(self.events_file, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def _save_scheduled_events(self):
        """Save scheduled events to cache"""
        with open(self.events_file, 'w') as f:
            json.dump(self._scheduled_events, f, indent=2, default=str)
    
    def add_scheduled_event(self, event_type: str, event_time: datetime, 
                           custom_name: str = None) -> bool:
        """
        Add a scheduled economic event.
        
        Args:
            event_type: One of HIGH_IMPACT_EVENTS keys
            event_time: When the event occurs
            custom_name: Optional custom name override
        """
        if event_type not in self.event_definitions:
            print(f"Unknown event type: {event_type}")
            return False
        
        event_def = self.event_definitions[event_type]
        
        event = {
            'type': event_type,
            'name': custom_name or event_def['name'],
            'time': event_time.isoformat(),
            'impact': event_def['impact'],
            'gold_correlation': event_def['gold_correlation'],
            'blackout_before': event_def['blackout_hours_before'],
            'blackout_after': event_def['blackout_hours_after'],
            'added_at': datetime.now().isoformat()
        }
        
        self._scheduled_events.append(event)
        self._save_scheduled_events()
        
        return True
    
    def get_upcoming_events(self, hours_ahead: int = 24) -> List[Dict]:
        """Get events scheduled in the next N hours"""
        now = datetime.now()
        cutoff = now + timedelta(hours=hours_ahead)
        
        upcoming = []
        for event in self._scheduled_events:
            try:
                event_time = datetime.fromisoformat(event['time'])
                if now <= event_time <= cutoff:
                    event['hours_until'] = (event_time - now).total_seconds() / 3600
                    upcoming.append(event)
            except:
                pass
        
        # Sort by time
        upcoming.sort(key=lambda x: x.get('hours_until', 999))
        
        return upcoming
    
    def is_in_blackout_period(self) -> Tuple[bool, Optional[Dict]]:
        """
        Check if we're currently in a trading blackout period.
        
        Returns:
            (is_blackout: bool, event: Dict or None)
        """
        now = datetime.now()
        
        for event in self._scheduled_events:
            try:
                event_time = datetime.fromisoformat(event['time'])
                
                # Calculate blackout window
                blackout_start = event_time - timedelta(hours=event['blackout_before'])
                blackout_end = event_time + timedelta(hours=event['blackout_after'])
                
                if blackout_start <= now <= blackout_end:
                    return True, event
            except:
                pass
        
        return False, None
    
    def get_risk_adjustment(self, hours_ahead: int = 4) -> Dict:
        """
        Calculate risk adjustment based on upcoming events.
        
        Returns:
            {
                'risk_multiplier': float (0.0 to 1.0),
                'reason': str,
                'upcoming_high_impact': List[Dict],
                'in_blackout': bool
            }
        """
        # Check blackout first
        in_blackout, blackout_event = self.is_in_blackout_period()
        
        if in_blackout:
            return {
                'risk_multiplier': 0.0,
                'reason': f"Blackout period: {blackout_event['name']}",
                'upcoming_high_impact': [blackout_event],
                'in_blackout': True
            }
        
        # Check upcoming events
        upcoming = self.get_upcoming_events(hours_ahead)
        
        if not upcoming:
            return {
                'risk_multiplier': 1.0,
                'reason': 'No imminent high-impact events',
                'upcoming_high_impact': [],
                'in_blackout': False
            }
        
        # Calculate risk reduction based on proximity
        min_multiplier = 1.0
        reason = ''
        high_impact = []
        
        for event in upcoming:
            hours_until = event.get('hours_until', 999)
            impact = event.get('impact', 'LOW')
            
            if impact == 'HIGH':
                high_impact.append(event)
                
                if hours_until < 1:
                    mult = 0.0  # Block trading
                    reason = f"HIGH: {event['name']} in {hours_until:.1f}h"
                elif hours_until < 2:
                    mult = 0.3
                    reason = f"Reduce risk: {event['name']} in {hours_until:.1f}h"
                elif hours_until < 4:
                    mult = 0.5
                    reason = f"Caution: {event['name']} in {hours_until:.1f}h"
                else:
                    mult = 0.8
                    reason = f"Upcoming: {event['name']} in {hours_until:.1f}h"
                
                min_multiplier = min(min_multiplier, mult)
            
            elif impact == 'MEDIUM':
                if hours_until < 1:
                    min_multiplier = min(min_multiplier, 0.5)
                    reason = f"MEDIUM: {event['name']} imminent"
        
        return {
            'risk_multiplier': min_multiplier,
            'reason': reason or 'Normal conditions',
            'upcoming_high_impact': high_impact,
            'in_blackout': False
        }
    
    def cleanup_past_events(self, keep_hours: int = 24):
        """Remove events that occurred more than N hours ago"""
        cutoff = datetime.now() - timedelta(hours=keep_hours)
        
        self._scheduled_events = [
            e for e in self._scheduled_events
            if datetime.fromisoformat(e['time']) > cutoff
        ]
        
        self._save_scheduled_events()
    
    def fetch_from_api(self, api_key: str = None) -> int:
        """
        Fetch upcoming events from Finnhub calendar API.
        Returns number of events added.
        
        Note: Requires Finnhub API key
        """
        if not api_key:
            api_key = os.environ.get('FINNHUB_API_KEY', '')
        
        if not api_key:
            print("  ⚠️ No API key for calendar fetch")
            return 0
        
        try:
            url = 'https://finnhub.io/api/v1/calendar/economic'
            params = {'token': api_key}
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                return 0
            
            data = response.json()
            events = data.get('economicCalendar', [])
            
            added = 0
            for e in events:
                # Map to our event types
                event_name = e.get('event', '').lower()
                impact = e.get('impact', 1)  # Finnhub uses 1-3
                
                # Determine event type
                event_type = None
                if 'fomc' in event_name or 'fed' in event_name:
                    event_type = 'FOMC_DECISION'
                elif 'cpi' in event_name or 'inflation' in event_name:
                    event_type = 'US_CPI'
                elif 'nonfarm' in event_name or 'payroll' in event_name:
                    event_type = 'US_NFP'
                elif 'gdp' in event_name:
                    event_type = 'US_GDP'
                elif 'ecb' in event_name:
                    event_type = 'ECB_DECISION'
                
                if event_type and impact >= 2:  # Medium or high impact
                    try:
                        event_time = datetime.fromisoformat(e.get('time', ''))
                        if event_time > datetime.now():
                            self.add_scheduled_event(event_type, event_time, e.get('event'))
                            added += 1
                    except:
                        pass
            
            return added
            
        except Exception as ex:
            print(f"  ❌ Calendar API error: {ex}")
            return 0
    
    def add_sample_events(self):
        """Add sample events for testing"""
        # Add some test events
        test_events = [
            ('FOMC_DECISION', datetime.now() + timedelta(hours=3)),
            ('US_CPI', datetime.now() + timedelta(hours=8)),
            ('US_NFP', datetime.now() + timedelta(days=2)),
        ]
        
        for event_type, event_time in test_events:
            self.add_scheduled_event(event_type, event_time)
        
        print(f"  ✓ Added {len(test_events)} sample events")


# Singleton instance
_calendar_instance = None

def get_economic_calendar() -> EconomicCalendar:
    """Get or create singleton EconomicCalendar"""
    global _calendar_instance
    if _calendar_instance is None:
        _calendar_instance = EconomicCalendar()
    return _calendar_instance


if __name__ == "__main__":
    # Test the economic calendar
    print("=" * 50)
    print("Economic Calendar Test")
    print("=" * 50)
    
    cal = EconomicCalendar()
    
    # Add sample events
    cal.add_sample_events()
    
    # Check upcoming
    upcoming = cal.get_upcoming_events(hours_ahead=72)
    print(f"\n📅 Upcoming events (next 72h):")
    for e in upcoming:
        print(f"   {e['name']} - in {e['hours_until']:.1f}h ({e['impact']})")
    
    # Check risk adjustment
    risk = cal.get_risk_adjustment()
    print(f"\n🛡️ Risk Adjustment:")
    print(f"   Multiplier: {risk['risk_multiplier']:.2f}")
    print(f"   Reason: {risk['reason']}")
    print(f"   In Blackout: {risk['in_blackout']}")








