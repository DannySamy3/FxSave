# Gold Price Prediction System (XAUUSD) v2.2

A complete **production-ready** machine learning system for predicting Gold price movements using Python XGBoost and Next.js frontend, enhanced with **live news integration**.

## 🎯 Features (v2.2)

### Core ML Features
- **Multi-Timeframe Predictions**: 15m, 30m, 1h, 4h, 1D
- **Probability Calibration**: Isotonic regression for realistic confidence scores
- **Calibration Drift Detection**: Warns when calibration shifts excessively

### Risk Management
- **Cascading HTF Validation**: 1D → 4H → 1H → 30m → 15m
- **Dynamic Position Sizing**: Based on volatility and account balance
- **Risk-Reward Enforcement**: Minimum 1:2 RR required
- **Regime-Aware Trading**: Only trades in trending markets

### Trading Rules
- **Standardized Rejection Codes**: Consistent messages across system
- **HTF Conflict Detection**: Hard conflicts block trades, soft conflicts reduce risk
- **No Martingale Logic**: Fixed risk percentages

### 📰 News Integration (v2.2 NEW)
- **Multi-Source News Fetching**: Finnhub, Alpha Vantage, NewsAPI
- **Sentiment Analysis**: Rule-based Gold-specific lexicon
- **High-Impact Event Detection**: Fed, CPI, NFP, geopolitical events
- **Economic Calendar**: Scheduled event tracking with blackout periods
- **Trade Blocking**: Automatically blocks trades during high-impact news
- **Risk Adjustment**: Reduces position size when news sentiment is uncertain

### UI & Logging
- **News Panel**: Live headlines with sentiment indicators
- **Clear NO TRADE Display**: Shows 0% risk with reason (including news blocks)
- **Forward Testing Logs**: Complete audit trail with all fields + news data
- **Position Size Calculator**: User-adjustable balance and risk %

## 📊 System Architecture

```
┌─────────────────────────────────────────────────────┐
│                 PYTHON BACKEND                       │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐    │
│  │ train.py   │  │ predict.py │  │ forward_   │    │
│  │ (Training) │  │ (Inference)│  │ test.py    │    │
│  └────────────┘  └────────────┘  └────────────┘    │
│         │              │               │            │
│  ┌──────▼──────────────▼───────────────▼──────┐    │
│  │              CORE MODULES                   │    │
│  │  ┌──────────┐ ┌──────────┐ ┌────────────┐ │    │
│  │  │calibration│ │  regime  │ │risk_engine │ │    │
│  │  └──────────┘ └──────────┘ └────────────┘ │    │
│  │  ┌──────────┐ ┌──────────┐                │    │
│  │  │ features │ │  rules   │                │    │
│  │  └──────────┘ └──────────┘                │    │
│  └────────────────────────────────────────────┘    │
└───────────────────────┬─────────────────────────────┘
                        │
                        ▼
              latest_prediction.json
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│                 NEXT.JS FRONTEND                     │
│  ┌────────────┐       ┌────────────────────────┐   │
│  │ /api/      │  ──▶  │ Dashboard (index.js)   │   │
│  │ predict.js │       │ - Multi-TF tabs        │   │
│  └────────────┘       │ - Trade/No-Trade UI    │   │
│                       │ - Position calculator  │   │
│                       └────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- **Node.js** >= 16.0.0
- **Python** >= 3.8
- **pip** (Python package manager)

### Step 1: Install Dependencies

```bash
# Node.js
npm install

# Python
cd python_model
pip install -r requirements.txt
```

### Step 2: Train Models (First Time)

```bash
cd python_model
python train.py
```

This will:
- Download historical Gold data from Yahoo Finance
- Train XGBoost models for each timeframe
- Calibrate probability outputs
- Save models and calibrators

### Step 3: Generate Predictions

```bash
# Batch mode (full data fetch)
cd python_model
python predict.py

# OR Live mode (incremental updates)
python predict.py --live
```

### Step 4: Start Frontend

```bash
npm run dev
```

Open **http://localhost:3000**

### Step 5: Verify System Health

```bash
cd python_model
python health_check.py
```

## 🔴 Live Prediction Mode

### Running Live Predictions

```bash
# Single live prediction
cd python_model
python live_predictor.py

# Continuous scheduler (runs predictions automatically)
python scheduler.py

# Scheduler with custom interval (check every 30s)
python scheduler.py --interval 30

# Single run then exit
python scheduler.py --once
```

### Live Mode Features

1. **Incremental Data**: Only fetches new candles (append-only)
2. **Data Caching**: Cached in `python_model/cache/`
3. **Auto-refresh UI**: Frontend polls for new predictions
4. **Market Hours Aware**: Skips predictions when market closed

### Rolling Retrain

```bash
# Weekly retrain with backup
cd python_model
python rolling_retrain.py

# Retrain without backup
python rolling_retrain.py --no-backup

# List backups
python rolling_retrain.py --list-backups

# Restore from backup
python rolling_retrain.py --restore backups/backup_20260104_120000
```

## 📁 Project Structure

```
gold-trade/
├── python_model/
│   ├── train.py              # Training script (v2.0)
│   ├── predict.py            # Prediction engine (v2.0)
│   ├── calibration.py        # Probability calibration
│   ├── regime.py             # Market regime detection
│   ├── risk_engine.py        # Position sizing & validation
│   ├── rules_engine.py       # Trade filtering rules
│   ├── forward_test.py       # Logging & paper trading
│   ├── features.py           # Technical indicators
│   ├── health_check.py       # System validation
│   ├── config.json           # All configuration
│   ├── requirements.txt      # Python dependencies
│   ├── xgb_*.pkl             # Trained models (per TF)
│   └── calibrator_*.pkl      # Calibrators (per TF)
│
├── pages/
│   ├── api/
│   │   ├── predict.js        # API endpoint
│   │   └── update-prediction.js
│   ├── index.js              # Main dashboard
│   ├── _app.js
│   └── _document.js
│
├── public/
│   └── latest_prediction.json  # Generated predictions
│
├── styles/
│   └── Home.module.css       # Dashboard styling
│
├── package.json
├── next.config.js
└── README.md
```

## 🔧 Configuration

All settings are in `python_model/config.json`:

```json
{
  "thresholds": {
    "min_confidence": 0.55,     // Minimum confidence to trade
    "high_confidence": 0.75
  },
  "rules": {
    "enable_regime_filter": true,
    "allowed_regimes": ["STRONG_TREND", "WEAK_TREND"]
  },
  "risk_management": {
    "account_balance": 10000,
    "base_risk_pct": 1.0,
    "max_risk_pct": 2.0,
    "min_rr_ratio": 2.0
  },
  "news": {
    "enabled": true,
    "short_term_hours": 2,
    "long_term_hours": 8,
    "high_impact_risk_multiplier": 0.0,
    "sentiment_confidence_factor": 0.03,
    "enable_blackouts": true
  }
}
```

## 📰 News API Setup (Optional)

The system works with mock news data when API keys are unavailable.
For live news, set environment variables:

```bash
# Windows (PowerShell)
$env:FINNHUB_API_KEY = "your_finnhub_key"
$env:ALPHA_VANTAGE_KEY = "your_alpha_vantage_key"
$env:NEWSAPI_KEY = "your_newsapi_key"

# Linux/Mac
export FINNHUB_API_KEY="your_finnhub_key"
export ALPHA_VANTAGE_KEY="your_alpha_vantage_key"
export NEWSAPI_KEY="your_newsapi_key"
```

Get free API keys from:
- **Finnhub**: https://finnhub.io/register (60 calls/min free)
- **Alpha Vantage**: https://www.alphavantage.co/support/#api-key (5 calls/min free)
- **NewsAPI**: https://newsapi.org/register (100 calls/day free)

## 🛡️ Rejection Codes

| Code | Meaning |
|------|---------|
| `LOW_CONFIDENCE` | Confidence below threshold (55%) |
| `HTF_CONFLICT` | Higher timeframe disagrees |
| `BAD_RR` | Risk:Reward below 1:2 |
| `RANGE_MARKET` | Market not trending |
| `HIGH_VOLATILITY` | Extreme ATR spike |
| `LOW_VOLATILITY` | Dead market |
| `HIGH_IMPACT_NEWS` | Major news event detected |
| `CALENDAR_BLACKOUT` | Economic event blackout period |
| `EVENT_IMMINENT` | Major event within 1 hour |

## 🔄 HTF Validation Flow

```
1D  ──validates──▶  4H  ──validates──▶  1H  ──validates──▶  30m  ──validates──▶  15m
```

- **Hard Conflict**: Parent TF direction differs in strong trend → Block trade (0% risk)
- **Soft Conflict**: Parent TF direction differs in weak trend → Reduce risk (50%)
- **Aligned**: All HTFs agree → Full risk allocation

## 📊 Forward Testing

All predictions are logged to `forward_test_log.csv`:

| Field | Description |
|-------|-------------|
| timestamp | When prediction was made |
| timeframe | 15m, 30m, 1h, 4h, 1d |
| direction | UP or DOWN |
| raw_conf | Raw model probability |
| calib_conf | Calibrated probability |
| regime | Market regime |
| htf_status | ALIGNED, SOFT_CONFLICT, HARD_CONFLICT |
| decision | TRADE or NO_TRADE |
| reason | Rejection code if NO_TRADE |
| lots | Position size |
| rr_ratio | Risk:Reward ratio |
| news_sentiment | Aggregated sentiment score |
| news_high_impact | Whether high-impact news present |
| news_headlines | Top news headlines (truncated) |

## 🔒 Risk Controls

1. **No Data Leakage**: TimeSeriesSplit for all CV
2. **Deterministic**: All random seeds fixed (42)
3. **Offline Ready**: Works without internet after training
4. **No Martingale**: Fixed risk percentages only
5. **HTF Validation**: Lower TF blocked if HTF conflicts

## ⚠️ Important Notes

1. **Retrain Monthly**: Run `train.py` monthly to capture new patterns
2. **Check Calibration**: Monitor calibration drift warnings
3. **Paper Trade First**: Use forward testing before live trading
4. **Not Financial Advice**: For educational purposes only

## 📞 Troubleshooting

### Model not found
```bash
cd python_model
python train.py
```

### Calibration drift warning
Retrain the model to recalibrate:
```bash
python train.py
```

### HTF Conflict blocking all trades
This is intentional. Wait for timeframes to align.

### Position calculator shows 0
Ensure trade is approved (not NO_TRADE).

## 📄 License

Open source for educational use.

## ⚠️ Disclaimer

This system is for **educational and research purposes only**. Past performance does not guarantee future results. Always conduct your own research before trading.

---

**Version**: 2.2.0  
**Last Updated**: January 2026  
**Status**: ✅ Production Ready (News-Aware)
