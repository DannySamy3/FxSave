# News TTL (Time-To-Live) Implementation - Summary

## Overview
Implemented strict TTL rules for news to eliminate phantom/outdated news signals that were blocking trades incorrectly (e.g., 750-minute-old Fed news still blocking gold trades).

## Implementation Details

### 1. Configuration (`config.json`)
Added news control configuration:
```json
"news_control": {
  "max_news_age_minutes": 60,
  "high_impact_block_minutes": 90,
  "stale_news_policy": "IGNORE"
}
```

**Definitions:**
- `max_news_age_minutes`: Maximum allowed age for any news item (60 minutes)
- `high_impact_block_minutes`: How long trading is blocked after a real high-impact event (90 minutes)
- `stale_news_policy`: Must be "IGNORE" - stale news never blocks trades

### 2. Mandatory Timestamp Validation
Every news item must include a valid timestamp:
- Checks multiple fields: `published`, `timestamp`, `timestamp_utc`, `time`
- If timestamp is missing → **discard immediately**
- If timestamp is invalid → **discard immediately**
- Supports ISO format, Unix timestamps, and timezone-aware strings

### 3. News Age Calculation (Hard Gate)
Before applying any news logic:
```python
news_age_minutes = (now_utc - news.timestamp_utc).total_seconds() / 60

if news_age_minutes > max_news_age_minutes:
    ignore_news()  # Stale news must never block trades
```

### 4. High-Impact News Blocking Window
Only fresh HIGH impact news can block trading:
```python
if (
    news.impact == "HIGH"
    and news_age_minutes <= high_impact_block_minutes
):
    block_trading(reason="HIGH_IMPACT_NEWS")
else:
    allow_trading()
```

**Key Rules:**
- Blocking window automatically expires after `high_impact_block_minutes`
- No manual reset required
- Stale news (>60 min) never creates blocks
- Blocks are automatically removed when they expire

### 5. Cache Invalidation (Critical Fix)
Strict cache expiry implemented:
```python
if cached_news_age_minutes > max_news_age_minutes:
    clear_news_cache()
```

**Rules:**
- No persistent news cache beyond TTL
- Cache must refresh on every trading cycle
- Stale cache → auto-purge
- Fresh news is filtered on every fetch

### 6. UI Messaging (Exact & Honest)

#### Stale News (Non-Blocking)
```
ℹ️ News Ignored
Reason: Data stale (750 minutes old)
Action: No trade restriction applied
```

#### Active High-Impact Block
```
🔴 TRADING BLOCKED
Reason: High-Impact News
Event Age: 12 minutes
Block Expires In: 78 minutes
```

#### Clean State
```
✅ News Check Passed
Fresh News: None
Trading Status: Allowed
```

### 7. Logging (Audit & Debug)
Every cycle logs:
- `news_present` (true/false)
- `news_age_minutes` (oldest news item age)
- `news_impact` (HIGH/MEDIUM/LOW)
- `news_cache_cleared` (true/false)
- `trade_blocked_by_news` (true/false)

All fields logged to forward test schema for audit trail.

### 8. Safety Guarantees

✅ **No stale news can block trades**
- News older than 60 minutes is automatically ignored
- Missing timestamps cause immediate discard

✅ **No indefinite news blocks**
- Blocks automatically expire after 90 minutes
- TTL validation runs on every check

✅ **No phantom Fed headlines**
- Timestamp validation prevents fake/old news
- Cache invalidation prevents stale data persistence

✅ **Deterministic behavior**
- Same input → same output
- No randomness or manual overrides

✅ **Automatic recovery**
- Expired blocks are automatically removed
- Stale cache is automatically cleared

## Files Modified

1. **`python_model/config.json`**
   - Added `news_control` section with TTL settings

2. **`python_model/news_blocker.py`**
   - Added `_validate_and_parse_timestamp()` method
   - Updated `detect_high_impact_news()` to enforce TTL
   - Updated `update_active_blocks()` to remove expired blocks
   - Updated `get_block_status()` to double-check TTL

3. **`python_model/news_integration.py`**
   - Added `_filter_stale_news()` method
   - Updated `refresh_news()` to clear stale cache
   - Enhanced `get_news_assessment()` with TTL logging
   - Updated `save_news_state()` to include TTL info

4. **`python_model/live_predictor.py`**
   - Added TTL logging fields to forward test log

5. **`pages/index.js`**
   - Added UI for stale news warnings
   - Added UI for active high-impact blocks
   - Added UI for clean state confirmation

6. **`pages/api/news.js`**
   - Enhanced freshness checking with `news_age_minutes`

## Acceptance Criteria Status

✅ Old news auto-expires  
✅ "750m old" news never blocks trades  
✅ Gold not blocked by non-existent Fed events  
✅ Cache clears correctly  
✅ UI shows real, time-bounded reasons  

## Core Principle

**If news cannot be proven fresh, it must be treated as nonexistent.**

The system prioritizes capital preservation by:
- Discarding news without timestamps
- Ignoring news older than TTL
- Automatically expiring blocks
- Clearing stale cache
- Providing honest UI messaging

All code is deterministic, audit-safe, and ready for production use.

