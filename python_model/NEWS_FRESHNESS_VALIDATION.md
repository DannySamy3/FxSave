# News Freshness Validation System

## Overview

This document describes the true recency validation system for news items in Gold-Trade Pro v2.2.0. The system implements dual timestamp tracking and stale context detection to ensure that only verifiably recent and genuinely new news events can block trades.

## Core Principles

**No trade may be blocked by news unless the news is:**
1. Verifiably recent (both timestamps fresh)
2. Genuinely new (not stale context)
3. Within the defined impact window

If these conditions are not satisfied, the system must proceed as if no high-impact news exists.

## Dual Timestamp Tracking

Every news item tracks two timestamps:

### 1. `origin_timestamp`
- When the news event actually occurred or was published
- Source: `origin_timestamp`, `published`, `timestamp`, `timestamp_utc`, or `time` fields
- Used for determining if the event is still relevant (impact relevance window)

### 2. `fetch_timestamp`
- When the system retrieved the news item
- Source: `fetch_timestamp` field or current fetch time
- Used for cache freshness validation (TTL enforcement)

## Classification System

News items are classified into four categories:

### `LIVE_EVENT`
- **Condition**: Both `origin_timestamp` and `fetch_timestamp` are fresh
- **Validation**:
  - `fetch_age_minutes <= max_news_age_minutes` (60 minutes)
  - `origin_age_minutes <= impact_relevance_window_minutes` (180 minutes)
- **Behavior**: Can block trades if HIGH impact

### `STALE_CONTEXT`
- **Condition**: `origin_timestamp` is old but `fetch_timestamp` is fresh
- **Validation**:
  - `fetch_age_minutes <= max_news_age_minutes` (60 minutes)
  - `origin_age_minutes > impact_relevance_window_minutes` (180 minutes)
- **Behavior**: **NEVER blocks trades** - treated as historical context

### `EXPIRED`
- **Condition**: `fetch_timestamp` expired (cache too old)
- **Validation**:
  - `fetch_age_minutes > max_news_age_minutes` (60 minutes)
- **Behavior**: **NEVER blocks trades** - cache expired

### `UNVERIFIED`
- **Condition**: Cannot verify freshness (missing timestamps)
- **Validation**: Missing `origin_timestamp` or `fetch_timestamp`
- **Behavior**: **NEVER blocks trades** - fail-safe behavior

## Configuration

Add to `config.json`:

```json
"news_control": {
  "max_news_age_minutes": 60,              // Cache TTL (fetch_timestamp)
  "high_impact_block_minutes": 90,          // Blocking window
  "stale_news_policy": "IGNORE",
  "impact_relevance_window_minutes": 180    // Event relevance window (origin_timestamp)
}
```

## Stale Context Detection

The system maintains a cache of seen events (`_seen_events`) to detect stale context:

1. **Event Signature**: Created from `news_type` and normalized headline
2. **Duplicate Detection**: If the same event is seen again with an older or equal `origin_timestamp`, it's classified as stale context
3. **Protection**: STALE_CONTEXT classification prevents old events from blocking trades

## Implementation Details

### NewsBlock Class

```python
class NewsBlock:
    def __init__(self, news_type, origin_timestamp, fetch_timestamp, 
                 source, headline, impact_level, classification):
        self.origin_timestamp = origin_timestamp
        self.fetch_timestamp = fetch_timestamp
        self.classification = classification  # LIVE_EVENT, STALE_CONTEXT, EXPIRED, UNVERIFIED
        # ... other fields
```

### Validation Logic

```python
def _validate_and_parse_timestamps(item, fetch_time):
    # Parse origin_timestamp and fetch_timestamp
    # Calculate ages
    fetch_age = (fetch_time - fetch_timestamp).total_seconds() / 60
    origin_age = (fetch_time - origin_timestamp).total_seconds() / 60
    
    # Classify
    if fetch_age > max_news_age_minutes:
        return EXPIRED
    if origin_age > impact_relevance_window_minutes:
        return STALE_CONTEXT
    return LIVE_EVENT
```

### Blocking Logic

Only `LIVE_EVENT` classification can create blocks:

```python
if classification == NewsClassification.LIVE_EVENT:
    # Create block
else:
    # STALE_CONTEXT, EXPIRED, UNVERIFIED cannot block
    # Fail-safe: proceed as if no high-impact news exists
```

## Logging

Enhanced logging includes:

- `news_classification`: LIVE_EVENT | STALE_CONTEXT | EXPIRED | UNVERIFIED
- `news_origin_timestamp`: When the event occurred/published
- `news_fetch_timestamp`: When the system retrieved it
- `cache_age_minutes`: Age of fetch_timestamp
- `news_age_minutes`: Maximum age of news items
- `trade_blocked_by_news`: Whether trade was blocked (only for LIVE_EVENT)

## Fail-Safe Behavior

If news freshness cannot be verified:
- Default to `NEWS_UNAVAILABLE` classification
- Do not assume high impact
- Allow technical and model-based evaluation to proceed normally
- Never block trades based on unverified news

## Deterministic Behavior

- Same inputs → same outputs
- Classification is deterministic based on timestamps
- Stale context detection prevents duplicate blocks
- No randomness in classification logic

## Testing

Test scenarios:

1. **Fresh News (LIVE_EVENT)**: Both timestamps fresh → Should block if HIGH impact
2. **Stale Origin (STALE_CONTEXT)**: Old origin, fresh fetch → Should NOT block
3. **Expired Cache (EXPIRED)**: Old fetch timestamp → Should NOT block
4. **Missing Timestamps (UNVERIFIED)**: Missing data → Should NOT block
5. **Duplicate Event (STALE_CONTEXT)**: Same event seen again → Should NOT block

## Compliance

✅ News >60 minutes (fetch) never blocks
✅ News >180 minutes (origin) never blocks
✅ STALE_CONTEXT never blocks
✅ EXPIRED never blocks
✅ UNVERIFIED never blocks
✅ Only LIVE_EVENT with HIGH impact can block
✅ Logs fully explain every decision
✅ Deterministic behavior guaranteed



