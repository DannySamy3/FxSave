/**
 * Gold Price Prediction Dashboard - Live Trading Edition v2.1
 * 
 * Features:
 * - Multi-timeframe predictions
 * - Live/rolling prediction support
 * - Auto-refresh capability
 * - HTF conflict display
 * - Position calculator
 * - System status monitoring
 */

import { useState, useEffect } from "react";
import styles from "../styles/Home.module.css";

// Standardized rejection messages
const REJECTION_MSG = {
  "LOW_CONFIDENCE": "Low Confidence Score",
  "HTF_CONFLICT": "Higher Timeframe Conflict",
  "BAD_RR": "Insufficient Reward/Risk Ratio",
  "HIGH_VOLATILITY": "Extreme Volatility (News/Crash)",
  "RANGE_MARKET": "Market in Range (No Trend)",
  "LOW_VOLATILITY": "Low Volatility (Dead Market)",
  "REGIME_FILTER": "Market Regime Unfavorable",
  "SL_TOO_TIGHT": "Stop Loss Too Tight",
  "ZERO_RISK": "Zero Risk Allocation",
  "LOT_CALC_ERROR": "Position Size Calculation Error",
  "INSUFFICIENT_DATA": "Insufficient Market Data",
  // News-related rejections
  "HIGH_IMPACT_NEWS": "High-Impact News Event",
  "CALENDAR_BLACKOUT": "Economic Calendar Blackout",
  "EVENT_IMMINENT": "Major Economic Event Imminent",
  "NEWS_NEGATIVE_SENTIMENT": "Strong Negative News Sentiment",
  "CALIBRATION_UNSTABLE": "Calibration Drift Exceeds Safe Limit",
  "CALIBRATION_WARNING": "Calibration Drift Warning"
};

// HTF status labels
const HTF_STATUS_LABELS = {
  "ALIGNED": "✅ Aligned",
  "SOFT_CONFLICT": "⚠️ Partial Conflict",
  "HARD_CONFLICT": "❌ HTF Conflict"
};

export default function Home() {
  const [data, setData] = useState(null);
  const [selectedTimeframe, setSelectedTimeframe] = useState("1h");
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  
  // Live mode state
  const [liveMode, setLiveMode] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(60); // seconds
  const [systemStatus, setSystemStatus] = useState(null);
  
  // Risk Management State
  const [accountBalance, setAccountBalance] = useState(10000);
  const [riskPercentage, setRiskPercentage] = useState(1);
  
  // News state
  const [newsData, setNewsData] = useState(null);
  const [showNewsPanel, setShowNewsPanel] = useState(true);
  
  // Economic Calendar state
  const [showCalendar, setShowCalendar] = useState(true);

  const TIMEFRAMES = ["15m", "30m", "1h", "4h", "1d"];

  // Fetch predictions - no dependencies to prevent loops
  const fetchPrediction = async (showLoading = true) => {
    try {
      if (showLoading) setLoading(true);
      const res = await fetch(`/api/predict?t=${Date.now()}`);
      if (!res.ok) throw new Error("Failed to load predictions");
      
      const json = await res.json();
      setData(json);
      setLastUpdate(new Date());
      setError(null);
      
      // Check if in live mode
      setLiveMode(json.mode === "live");
      
    } catch (err) {
      console.error(err);
      setError("Failed to load prediction data.");
    } finally {
      setLoading(false);
    }
  };

  // Fetch system status
  const fetchStatus = async () => {
    try {
      const res = await fetch("/api/status");
      if (res.ok) {
        const status = await res.json();
        setSystemStatus(status);
      }
    } catch (err) {
      console.error("Status fetch error:", err);
    }
  };

  // Fetch news data
  const fetchNews = async () => {
    try {
      const res = await fetch("/api/news");
      if (res.ok) {
        const news = await res.json();
        setNewsData(news);
      }
    } catch (err) {
      console.error("News fetch error:", err);
    }
  };

  // Initial load only - runs once
  useEffect(() => {
    fetchPrediction(true);
    fetchStatus();
    fetchNews();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-refresh setup - separate effect
  useEffect(() => {
    if (!autoRefresh) return;
    
    const predictionInterval = setInterval(() => {
      fetchPrediction(false);
    }, refreshInterval * 1000);
    
    const statusInterval = setInterval(fetchStatus, 30000);
    const newsInterval = setInterval(fetchNews, 60000); // Refresh news every minute
    
    return () => {
      clearInterval(predictionInterval);
      clearInterval(statusInterval);
      clearInterval(newsInterval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRefresh, refreshInterval]);

  // Manual refresh (batch mode)
  const handleBatchUpdate = async () => {
    try {
      setUpdating(true);
      setError(null);
      const res = await fetch("/api/update-prediction", { method: "POST" });
      if (!res.ok) throw new Error("Update failed");
      await fetchPrediction();
    } catch (err) {
      setError(err.message);
    } finally {
      setUpdating(false);
    }
  };

  // Live prediction trigger
  const handleLiveUpdate = async () => {
    try {
      setUpdating(true);
      setError(null);
      const res = await fetch("/api/live-predict", { method: "POST" });
      if (!res.ok) throw new Error("Live prediction failed");
      
      const result = await res.json();
      if (result.predictions) {
        setData(result.predictions);
        setLastUpdate(new Date());
        setLiveMode(true);
      } else {
        await fetchPrediction();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setUpdating(false);
    }
  };

  // Position size calculator
  const calculatePositionSize = (setup) => {
    if (!setup || !setup.stop_distance || setup.stop_distance <= 0) {
      return "0.00";
    }
    
    const riskAmount = (accountBalance * riskPercentage) / 100;
    const contractSize = 100;
    const stopDist = parseFloat(setup.stop_distance);
    
    const lots = riskAmount / (stopDist * contractSize);
    return Math.max(0.01, Math.floor(lots * 100) / 100).toFixed(2);
  };

  // Get human-readable rejection message
  const getRejectionMessage = (code) => {
    if (!code) return "Unknown";
    return REJECTION_MSG[code] || code;
  };

  // Format time since last update
  const getTimeSinceUpdate = () => {
    if (!lastUpdate) return "Never";
    const seconds = Math.floor((new Date() - lastUpdate) / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ago`;
  };

  // Get current timeframe data
  const currentTF = data?.predictions?.[selectedTimeframe];
  const hasCalibrationWarning = currentTF && currentTF.calibration_drift > 15;
  
  // Helper for sentiment color
  const getSentimentColor = (score) => {
    if (score > 0.2) return '#16a34a'; // green
    if (score < -0.2) return '#dc2626'; // red
    return '#6b7280'; // gray
  };
  
  // Helper for sentiment label
  const getSentimentIcon = (label) => {
    if (label === 'BULLISH') return '📈';
    if (label === 'BEARISH') return '📉';
    return '➡️';
  };
  
  // Check if news is blocking trades
  const newsBlocksTrade = newsData && !newsData.can_trade;

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1>🥇 Gold Price</h1>
        <p className={styles.subtitle}>
          {liveMode ? "🔴 LIVE" : "📦 BATCH"} • Multi-Timeframe AI
        </p>
      </header>

      {/* LEFT SIDEBAR - Navigation */}
      <aside className={styles.sidebar}>
        {/* Predictions Section */}
        <div className={styles.sidebarSection}>
          <div className={styles.sectionTitle}>Predictions</div>
          {TIMEFRAMES.map((tf) => {
            const tfData = data?.predictions?.[tf];
            const isActive = selectedTimeframe === tf;
            const isNoTrade = tfData?.decision === "NO_TRADE";
            const direction = tfData?.direction || "?";
            const confidence = tfData?.confidence || 0;
            
            return (
              <button
                key={tf}
                className={`${styles.navButton} ${isActive ? styles.active : ''}`}
                onClick={() => setSelectedTimeframe(tf)}
                title={`${tf} - ${direction} ${confidence.toFixed(1)}%`}
              >
                <span>{tf.toUpperCase()}</span>
                <span style={{marginLeft: 'auto', fontSize: '0.8rem'}}>
                  {direction} {confidence.toFixed(0)}%
                </span>
                {isNoTrade && (
                  <span className={styles.statusBadge}>
                    ⛔
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* System Status */}
        <div className={styles.sidebarSection}>
          <div className={styles.sectionTitle}>System</div>
          <div className={styles.systemStatus}>
            <h4>Status</h4>
            <div className={styles.statusItem}>
              <span>Mode</span>
              <span style={{fontWeight: 600}}>{liveMode ? '🔴 Live' : '📦 Batch'}</span>
            </div>
            <div className={styles.statusItem}>
              <span>Updated</span>
              <span style={{fontWeight: 600, fontSize: '0.75rem'}}>{getTimeSinceUpdate()}</span>
            </div>
            <div className={styles.statusItem}>
              <span>Auto-Refresh</span>
              <span style={{fontWeight: 600}}>
                {autoRefresh ? `${refreshInterval}s` : 'OFF'}
              </span>
            </div>
          </div>
        </div>

        {/* Controls Section */}
        <div className={styles.sidebarSection}>
          <div className={styles.sectionTitle}>Controls</div>
          <label className={styles.navButton} style={{marginBottom: '10px', cursor: 'pointer'}}>
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              style={{width: '16px', height: '16px'}}
            />
            <span>Auto-Refresh</span>
          </label>
          <select 
            value={refreshInterval} 
            onChange={(e) => setRefreshInterval(Number(e.target.value))}
            className={styles.navButton}
            style={{
              background: 'rgba(255,255,255,0.1)',
              marginBottom: '10px',
              padding: '10px 12px'
            }}
            disabled={!autoRefresh}
          >
            <option value={30}>30s</option>
            <option value={60}>1m</option>
            <option value={300}>5m</option>
            <option value={900}>15m</option>
          </select>
          <button 
            className={styles.navButton}
            onClick={handleBatchUpdate} 
            disabled={updating}
            style={{marginBottom: '6px', opacity: updating ? 0.5 : 1}}
          >
            📦 Batch
          </button>
          <button 
            className={styles.navButton}
            onClick={handleLiveUpdate} 
            disabled={updating}
            style={{opacity: updating ? 0.5 : 1}}
          >
            🔴 Live
          </button>
        </div>

        {/* Risk Management */}
        <div className={styles.sidebarSection}>
          <div className={styles.sectionTitle}>Risk</div>
          <div style={{padding: '0 10px'}}>
            <label style={{display: 'block', fontSize: '0.8rem', color: 'rgba(255,255,255,0.7)', marginBottom: '6px', fontWeight: 500}}>
              Account Balance
            </label>
            <input 
              type="number"
              value={accountBalance}
              onChange={(e) => setAccountBalance(Number(e.target.value))}
              style={{
                width: '100%',
                padding: '8px',
                borderRadius: '6px',
                border: '1px solid rgba(255,255,255,0.2)',
                background: 'rgba(255,255,255,0.05)',
                color: 'white',
                marginBottom: '12px',
                fontSize: '0.9rem'
              }}
            />
            <label style={{display: 'block', fontSize: '0.8rem', color: 'rgba(255,255,255,0.7)', marginBottom: '6px', fontWeight: 500}}>
              Risk Per Trade
            </label>
            <div style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
              <input 
                type="range"
                min="0.1"
                max="5"
                step="0.1"
                value={riskPercentage}
                onChange={(e) => setRiskPercentage(Number(e.target.value))}
                style={{flex: 1}}
              />
              <span style={{color: '#ffd700', fontWeight: 600, fontSize: '0.9rem', minWidth: '30px'}}>
                {riskPercentage.toFixed(1)}%
              </span>
            </div>
          </div>
        </div>
      </aside>

      {/* MAIN CONTENT */}
      <main className={styles.main}>
        <div className={styles.contentArea}>
          {/* Loading State */}
          {loading && !data && (
            <div className={styles.card}>
              <div className={styles.loadingSpinner}>
                <div className={styles.spinner}></div>
                <p>Loading market data...</p>
              </div>
            </div>
          )}

          {/* Updating Overlay */}
          {updating && (
            <div className={styles.overlay}>
              <div className={styles.card}>
                <div className={styles.loadingSpinner}>
                  <div className={styles.spinner}></div>
                  <p>{liveMode ? "Running Live Prediction..." : "Analyzing Market Data..."}</p>
                  <small>Fetching data and running XGBoost models</small>
                </div>
              </div>
            </div>
          )}

          {/* Error Display */}
          {error && (
            <div className={styles.card}>
              <div className={styles.errorBox}>
                <p>⚠️ {error}</p>
                <div className={styles.errorActions}>
                  <button onClick={handleBatchUpdate} className={styles.retryButton}>Batch Update</button>
                  <button onClick={handleLiveUpdate} className={styles.retryButton}>Live Update</button>
                </div>
              </div>
            </div>
          )}

          {currentTF && !loading && !updating && (
            <>
              {/* Timeframe Tabs */}
              <div className={styles.timeframeTabs}>
                {TIMEFRAMES.map((tf) => {
                  const tfData = data?.predictions?.[tf];
                  const isNoTrade = tfData?.decision === "NO_TRADE";
                  const hasConflict = tfData?.htf_status === "HARD_CONFLICT";
                  return (
                    <button
                      key={tf}
                      className={`${styles.tabButton} ${selectedTimeframe === tf ? styles.activeTab : ''} ${isNoTrade ? styles.noTradeTab : ''}`}
                      onClick={() => setSelectedTimeframe(tf)}
                    >
                      {tf.toUpperCase()}
                      {isNoTrade && <span className={styles.tabIndicator}>{hasConflict ? "🔗" : "⛔"}</span>}
                    </button>
                  );
                })}
              </div>

              {/* Stale News Warning */}
              {newsData && newsData.news_stale && newsData.news_age_minutes && (
                <div className={styles.warningBanner} style={{backgroundColor: '#fef3c7', borderColor: '#f59e0b'}}>
                  ℹ️ News Ignored ({Math.round(newsData.news_age_minutes)} min old) • No restrictions applied
                </div>
              )}

              {/* High-Impact Block */}
              {newsBlocksTrade && newsData.news_block && (
                <div className={styles.newsBlockBanner}>
                  🔴 TRADING BLOCKED • High-Impact News
                  {newsData.news_block.block_expires_in_minutes && (
                    <br />
                  )}
                  Block Expires: {Math.round(newsData.news_block.block_expires_in_minutes)} min
                </div>
              )}

              {/* News Check Passed */}
              {newsData && !newsBlocksTrade && !newsData.news_stale && (
                <div className={styles.warningBanner} style={{backgroundColor: '#d1fae5', borderColor: '#10b981'}}>
                  ✅ News Check Passed • {newsData.headlines?.length || 0} items
                </div>
              )}

              {/* Main Prediction Card */}
              <div className={`${styles.card} ${styles.mainCard}`}>
                {currentTF.decision !== "TRADE" ? (
                  <div className={styles.rejectionBanner}>
                    <h3>⛔ NO TRADE</h3>
                    <div className={styles.rejectionDetails}>
                      <div className={styles.rejectionRow}>
                        <span>Decision:</span>
                        <strong>NO_TRADE</strong>
                      </div>
                      <div className={styles.rejectionRow}>
                        <span>Risk Allocation:</span>
                        <strong>0%</strong>
                      </div>
                      <div className={styles.rejectionRow}>
                        <span>Capital at Risk:</span>
                        <strong>$0.00</strong>
                      </div>
                      <div className={styles.rejectionRow}>
                        <span>Reason:</span>
                        <strong style={{color: '#b91c1c'}}>
                          {getRejectionMessage(currentTF.rejection_reason)}
                        </strong>
                      </div>
                    </div>
                    <div className={styles.noTradeInfo}>
                      <small>
                        Model predicted <strong>{currentTF.direction}</strong> with {currentTF.confidence}% confidence (blocked by rules)
                      </small>
                    </div>
                  </div>
                ) : (
                  <div className={`${styles.predictionBox} ${currentTF.direction === "UP" ? styles.predictionUp : styles.predictionDown}`}>
                    <div className={styles.predictionArrow}>
                      {currentTF.direction === "UP" ? "📈" : "📉"}
                    </div>
                    <div className={styles.predictionText}>
                      <h2>{currentTF.direction}</h2>
                      <p className={styles.confidence}>{currentTF.confidence}% Confidence</p>
                      {currentTF.htf_status === 'SOFT_CONFLICT' && (
                        <small className={styles.softConflict}>⚠️ Risk reduced (HTF partial conflict)</small>
                      )}
                    </div>
                  </div>
                )}

                <div className={styles.priceInfo}>
                  <div className={styles.priceBox}>
                    <label>Current Price</label>
                    <span>${currentTF.current_price}</span>
                  </div>
                  <div className={styles.priceBox}>
                    <label>Market Regime</label>
                    <span className={styles.regimeTag}>{currentTF.regime || "UNKNOWN"}</span>
                  </div>
                </div>

                {/* HTF Alignment Status */}
                {currentTF.htf_status && (
                  <div className={styles.htfStatus}>
                    <label>HTF Alignment</label>
                    <span className={`${styles.htfBadge} ${styles[`htf${currentTF.htf_status}`]}`}>
                      {HTF_STATUS_LABELS[currentTF.htf_status] || currentTF.htf_status}
                    </span>
                  </div>
                )}
              </div>

              {/* Trade Setup Card */}
              {currentTF.decision === "TRADE" && currentTF.setup && (
                <div className={styles.card}>
                  <h3>🎯 Trade Setup ({selectedTimeframe})</h3>
                  <div className={styles.setupGrid}>
                    <div className={styles.setupItem}>
                      <label>ENTRY</label>
                      <span className={styles.entryPrice}>${currentTF.setup.entry}</span>
                    </div>
                    <div className={styles.setupItem}>
                      <label>STOP LOSS</label>
                      <span className={styles.slPrice}>${currentTF.setup.sl}</span>
                    </div>
                    <div className={styles.setupItem}>
                      <label>TAKE PROFIT</label>
                      <span className={styles.tpPrice}>${currentTF.setup.tp}</span>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </main>

      {/* RIGHT SIDEBAR - Quick Stats */}
      <aside className={styles.rightSidebar}>
        {/* Quick Stats */}
        <div className={styles.miniCard}>
          <h4>📊 Quick Stats</h4>
          <label>Total Signals</label>
          <span>{data?.prediction_count || 0}</span>
          <small>All timeframes combined</small>
        </div>

        {/* Current Price */}
        <div className={styles.miniCard}>
          <h4>💰 Current Price</h4>
          <label>Gold (GC=F)</label>
          <span>${currentTF?.current_price || "-"}</span>
          <small>Live market data</small>
        </div>

        {/* Position Calculator */}
        {currentTF?.decision === "TRADE" && currentTF?.setup && (
          <div className={styles.miniCard}>
            <h4>📍 Position Size</h4>
            <label>Recommended Lots</label>
            <span>{calculatePositionSize(currentTF.setup)}</span>
            <small>Based on {riskPercentage.toFixed(1)}% risk</small>
          </div>
        )}

        {/* News Status */}
        {newsData && (
          <div className={styles.miniCard}>
            <h4>{newsBlocksTrade ? '🔴' : '✅'} News Status</h4>
            <label>Trading Status</label>
            <span>{newsBlocksTrade ? 'BLOCKED' : 'ALLOWED'}</span>
            <small>{newsData.headlines?.length || 0} news items</small>
          </div>
        )}

        {/* Risk Management */}
        <div className={styles.miniCard}>
          <h4>⚠️ Risk Info</h4>
          <label>Account</label>
          <span>${accountBalance}</span>
          <small>Risk per trade: {riskPercentage.toFixed(1)}%</small>
        </div>

        {/* System Info */}
        {systemStatus && (
          <div className={styles.miniCard}>
            <h4>🔧 System</h4>
            <label>Version</label>
            <span>{systemStatus.version || "2.2.0"}</span>
            <small>Last updated: {getTimeSinceUpdate()}</small>
          </div>
        )}
      </aside>
    </div>
  );
}

              Updated: {getTimeSinceUpdate()}
            </span>
          </div>
          <div className={styles.controlRight}>
            <label className={styles.autoRefreshToggle}>
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
              />
              <span>Auto-refresh</span>
            </label>
            <select 
              value={refreshInterval} 
              onChange={(e) => setRefreshInterval(Number(e.target.value))}
              className={styles.intervalSelect}
              disabled={!autoRefresh}
            >
              <option value={30}>30s</option>
              <option value={60}>1m</option>
              <option value={300}>5m</option>
              <option value={900}>15m</option>
            </select>
          </div>
        </div>

        {/* Timeframe Selector Tabs */}
        <div className={styles.timeframeTabs}>
          {TIMEFRAMES.map((tf) => {
            const tfData = data?.predictions?.[tf];
            const isNoTrade = tfData?.decision === "NO_TRADE";
            const hasConflict = tfData?.htf_status === "HARD_CONFLICT";
            return (
              <button
                key={tf}
                className={`${styles.tabButton} ${selectedTimeframe === tf ? styles.activeTab : ''} ${isNoTrade ? styles.noTradeTab : ''}`}
                onClick={() => setSelectedTimeframe(tf)}
              >
                {tf.toUpperCase()}
                {isNoTrade && <span className={styles.tabIndicator}>{hasConflict ? "🔗" : "⛔"}</span>}
              </button>
            );
          })}
        </div>

        {/* Loading State */}
        {loading && !data && (
          <div className={styles.card}>
            <div className={styles.loadingSpinner}>
              <div className={styles.spinner}></div>
              <p>Loading market data...</p>
            </div>
          </div>
        )}

        {/* Updating Overlay */}
        {updating && (
          <div className={styles.overlay}>
             <div className={styles.card}>
              <div className={styles.loadingSpinner}>
                <div className={styles.spinner}></div>
                <p>{liveMode ? "Running Live Prediction..." : "Analyzing Market Data..."}</p>
                <small>Fetching data and running XGBoost models</small>
              </div>
            </div>
          </div>
        )}

        {/* Error Display */}
        {error && (
            <div className={styles.card}>
              <div className={styles.errorBox}>
                <p>⚠️ {error}</p>
                <div className={styles.errorActions}>
                  <button onClick={handleBatchUpdate} className={styles.retryButton}>Batch Update</button>
                  <button onClick={handleLiveUpdate} className={styles.retryButton}>Live Update</button>
                </div>
              </div>
            </div>
        )}

        {currentTF && !loading && !updating && (
          <>
            {/* Stale News Warning (Non-Blocking) */}
            {newsData && newsData.news_stale && newsData.news_age_minutes && (
              <div className={styles.warningBanner} style={{backgroundColor: '#fef3c7', borderColor: '#f59e0b'}}>
                ℹ️ News Ignored
                <br />
                Reason: Data stale ({Math.round(newsData.news_age_minutes)} minutes old)
                <br />
                Action: No trade restriction applied
              </div>
            )}

            {/* Active High-Impact Block */}
            {newsBlocksTrade && newsData.news_block && (
              <div className={styles.newsBlockBanner}>
                🔴 TRADING BLOCKED
                <br />
                Reason: High-Impact News
                <br />
                {newsData.news_block.event_age_minutes && (
                  <>
                    Event Age: {Math.round(newsData.news_block.event_age_minutes)} minutes
                    <br />
                  </>
                )}
                {newsData.news_block.block_expires_in_minutes && (
                  <>
                    Block Expires In: {Math.round(newsData.news_block.block_expires_in_minutes)} minutes
                  </>
                )}
              </div>
            )}

            {/* Clean State - News Check Passed */}
            {newsData && !newsBlocksTrade && !newsData.news_stale && (
              <div className={styles.warningBanner} style={{backgroundColor: '#d1fae5', borderColor: '#10b981'}}>
                ✅ News Check Passed
                <br />
                Fresh News: {newsData.headlines?.length || 0} items
                <br />
                Trading Status: Allowed
              </div>
            )}

            {/* Calibration Drift Warning (Risk Reduced) */}
            {currentTF.decision === "TRADE" && currentTF.drift_level === "WARNING" && (
              <div className={styles.warningBanner}>
                ⚠️ Risk Reduced
                <br />
                Decision: TRADE_ALLOWED
                <br />
                Reason: Calibration Drift ({currentTF.calibration_drift}%)
                <br />
                Risk Adjustment: 50%
              </div>
            )}

            {/* Calibration Drift Block (Critical) */}
            {currentTF.rejection_reason === "CALIBRATION_UNSTABLE" && (
              <div className={styles.newsBlockBanner}>
                ⛔ NO TRADE
                <br />
                Decision: NO_TRADE
                <br />
                Risk Allocation: 0%
                <br />
                Capital at Risk: $0.00
                <br />
                Reason: CALIBRATION_UNSTABLE
                <br />
                Details: Drift exceeds safe limit
              </div>
            )}

            {/* Main Prediction Card */}
            <div className={`${styles.card} ${styles.mainCard}`}>
              
              {/* Decision Badge */}
              {currentTF.decision !== "TRADE" ? (
                <div className={styles.rejectionBanner}>
                  <h3>⛔ NO TRADE</h3>
                  
                  <div className={styles.rejectionDetails}>
                    <div className={styles.rejectionRow}>
                       <span>Decision:</span>
                       <strong>NO_TRADE</strong>
                    </div>
                    <div className={styles.rejectionRow}>
                       <span>Risk Allocation:</span>
                       <strong>0%</strong>
                    </div>
                    <div className={styles.rejectionRow}>
                       <span>Capital at Risk:</span>
                       <strong>$0.00</strong>
                    </div>
                    <div className={styles.rejectionRow}>
                       <span>Reason:</span>
                       <strong style={{color: '#b91c1c'}}>
                         {getRejectionMessage(currentTF.rejection_reason)}
                       </strong>
                    </div>
                    {/* Show news block details if HIGH_IMPACT_NEWS */}
                    {currentTF.rejection_reason === "HIGH_IMPACT_NEWS" && currentTF.news?.block_status && (
                      <div className={styles.rejectionRow}>
                        <span>Details:</span>
                        <strong style={{color: '#dc2626'}}>
                          {currentTF.news.block_status.details || 
                           currentTF.news.block_status.ui_wording?.details || 
                           "High-impact news – cooldown active"}
                        </strong>
                      </div>
                    )}
                    {/* Show calibration drift details if CALIBRATION_UNSTABLE */}
                    {currentTF.rejection_reason === "CALIBRATION_UNSTABLE" && (
                      <div className={styles.rejectionRow}>
                        <span>Details:</span>
                        <strong style={{color: '#dc2626'}}>
                          Drift exceeds safe limit ({currentTF.calibration_drift}% drift)
                        </strong>
                      </div>
                    )}
                    {/* Show calibration drift warning if present */}
                    {currentTF.drift_level === "WARNING" && currentTF.decision === "TRADE" && (
                      <div className={styles.rejectionRow}>
                        <span>Calibration Drift:</span>
                        <strong style={{color: '#f59e0b'}}>
                          ⚠️ {currentTF.calibration_drift}% (Risk Reduced)
                        </strong>
                      </div>
                    )}
                    {currentTF.htf_status && currentTF.htf_status !== 'ALIGNED' && (
                      <div className={styles.rejectionRow}>
                        <span>HTF Status:</span>
                        <strong>{HTF_STATUS_LABELS[currentTF.htf_status] || currentTF.htf_status}</strong>
                      </div>
                    )}
                    {currentTF.news && (
                      <div className={styles.rejectionRow}>
                        <span>News Sentiment:</span>
                        <strong style={{color: getSentimentColor(currentTF.news.sentiment_score)}}>
                          {getSentimentIcon(currentTF.news.sentiment_label)} {currentTF.news.sentiment_label}
                        </strong>
                      </div>
                    )}
                  </div>
                  
                  <div className={styles.noTradeInfo}>
                    <small>
                      Model predicted <strong>{currentTF.direction}</strong> with {currentTF.confidence}% confidence
                      (blocked by rules)
                    </small>
                  </div>
                </div>
              ) : (
                <div className={`${styles.predictionBox} ${currentTF.direction === "UP" ? styles.predictionUp : styles.predictionDown}`}>
                  <div className={styles.predictionArrow}>
                    {currentTF.direction === "UP" ? "📈" : "📉"}
                  </div>
                  <div className={styles.predictionText}>
                    <h2>{currentTF.direction}</h2>
                    <p className={styles.confidence}>{currentTF.confidence}% Confidence</p>
                    {currentTF.htf_status === 'SOFT_CONFLICT' && (
                      <small className={styles.softConflict}>⚠️ Risk reduced (HTF partial conflict)</small>
                    )}
                    {currentTF.drift_level === 'WARNING' && (
                      <small className={styles.softConflict}>⚠️ Risk reduced (Calibration drift: {currentTF.calibration_drift}%)</small>
                    )}
                  </div>
                </div>
              )}

              <div className={styles.priceInfo}>
                <div className={styles.priceBox}>
                  <label>Current Price</label>
                  <span>${currentTF.current_price}</span>
                </div>
                <div className={styles.priceBox}>
                  <label>Market Regime</label>
                  <span className={styles.regimeTag}>{currentTF.regime || "UNKNOWN"}</span>
                </div>
              </div>

              {/* HTF Alignment Status */}
              {currentTF.htf_status && (
                <div className={styles.htfStatus}>
                  <label>HTF Alignment</label>
                  <span className={`${styles.htfBadge} ${styles[`htf${currentTF.htf_status}`]}`}>
                    {HTF_STATUS_LABELS[currentTF.htf_status] || currentTF.htf_status}
                  </span>
                  {currentTF.htf_details?.parent && (
                    <small>vs {currentTF.htf_details.parent.toUpperCase()}</small>
                  )}
                </div>
              )}

              {/* Action Buttons */}
              <div className={styles.actionButtons}>
                <button 
                  className={`${styles.refreshButton} ${styles.batchButton}`} 
                  onClick={handleBatchUpdate} 
                  disabled={updating}
                >
                  📦 Batch Refresh
                </button>
                <button 
                  className={`${styles.refreshButton} ${styles.liveButton}`} 
                  onClick={handleLiveUpdate} 
                  disabled={updating}
                >
                  🔴 Live Update
                </button>
              </div>
            </div>

            {/* Trade Setup Card */}
            {currentTF.decision === "TRADE" && currentTF.setup && (
            <div className={styles.card}>
              <h3>🎯 Trade Setup ({selectedTimeframe})</h3>
              <div className={styles.setupGrid}>
                <div className={styles.setupItem}>
                  <label>ENTRY</label>
                  <span className={styles.entryPrice}>${currentTF.setup.entry}</span>
                </div>
                <div className={styles.setupItem}>
                  <label>STOP LOSS</label>
                  <span className={styles.slPrice}>${currentTF.setup.sl}</span>
                </div>
                 <div className={styles.setupItem}>
                  <label>TAKE PROFIT</label>
                  <span className={styles.tpPrice}>${currentTF.setup.tp}</span>
                </div>
              </div>
              
              <div className={styles.riskGrid} style={{marginTop: '15px'}}>
                 <div className={styles.setupItem} style={{background: '#eff6ff', borderColor: '#bfdbfe'}}>
                  <label>RECOMMENDED LOTS</label>
                  <span style={{color: '#1e40af'}}>{currentTF.setup.lots}</span>
                </div>
                <div className={styles.setupItem}>
                  <label>RISK AMOUNT</label>
                  <span>${currentTF.setup.risk_amount}</span>
                </div>
                <div className={styles.setupItem}>
                  <label>RR RATIO</label>
                  <span>1:{currentTF.setup.rr_ratio}</span>
                </div>
              </div>

              <div className={styles.setupDetails}>
                <div className={styles.detailRow}>
                  <span>Stop Distance:</span>
                  <strong>${currentTF.setup.stop_distance}</strong>
                </div>
                <div className={styles.detailRow}>
                  <span>Risk %:</span>
                  <strong>{currentTF.setup.risk_pct}%</strong>
                </div>
                {currentTF.setup.htf_multiplier < 1 && (
                  <div className={styles.detailRow}>
                    <span>HTF Risk Adj:</span>
                    <strong>{(currentTF.setup.htf_multiplier * 100).toFixed(0)}%</strong>
                  </div>
                )}
              </div>
            </div>
            )}
            
            {/* Position Calculator */}
            {currentTF.decision === "TRADE" && currentTF.setup && (
            <div className={styles.card}>
              <h3>🛡️ Position Size Calculator</h3>
              <div className={styles.riskInputRow}>
                <div className={styles.inputGroup}>
                  <label>Account Balance ($)</label>
                  <input 
                    type="number" 
                    value={accountBalance} 
                    onChange={(e) => setAccountBalance(Number(e.target.value))}
                    min="0"
                    step="100"
                  />
                </div>
                <div className={styles.inputGroup}>
                  <label>Risk (%)</label>
                  <input 
                    type="number" 
                    value={riskPercentage} 
                    onChange={(e) => setRiskPercentage(Number(e.target.value))}
                    min="0.1"
                    max="10"
                    step="0.1"
                  />
                </div>
              </div>
              <div className={styles.positionResult}>
                <span>Calculated Position Size:</span>
                <strong>{calculatePositionSize(currentTF.setup)} Lots</strong>
              </div>
              <div className={styles.riskSummary}>
                <small>
                  Risking ${((accountBalance * riskPercentage) / 100).toFixed(2)} with 
                  ${currentTF.setup.stop_distance} stop = {calculatePositionSize(currentTF.setup)} lots
                </small>
              </div>
            </div>
            )}

            {/* Confidence Details */}
            <div className={styles.card}>
              <h3>📊 Confidence Breakdown</h3>
              <div className={styles.confGrid}>
                <div className={styles.confItem}>
                  <label>Raw Confidence</label>
                  <span>{currentTF.raw_confidence || currentTF.confidence}%</span>
                </div>
                <div className={styles.confItem}>
                  <label>Calibrated Confidence</label>
                  <span>{currentTF.confidence}%</span>
                </div>
                <div className={styles.confItem}>
                  <label>Calibration Drift</label>
                  <span className={currentTF.calibration_drift > 15 ? styles.driftWarning : ''}>
                    {currentTF.calibration_drift || 0}%
                  </span>
                </div>
              </div>
              
              {/* Candle timestamp */}
              {currentTF.candle_time && (
                <div className={styles.candleTime}>
                  <small>Candle: {new Date(currentTF.candle_time).toLocaleString()}</small>
                </div>
              )}
            </div>
          </>
        )}
        
        {!currentTF && !loading && !error && data && (
            <div className={styles.card}>
               <p>No prediction data available for {selectedTimeframe}. Try refreshing.</p>
            </div>
        )}

        {/* News Panel */}
        {newsData?.available && showNewsPanel && (
          <div className={`${styles.card} ${styles.newsCard}`}>
            <div className={styles.newsHeader}>
              <h3>📰 News & Events</h3>
              <button 
                className={styles.toggleButton}
                onClick={() => setShowNewsPanel(false)}
              >
                Hide
              </button>
            </div>
            
            {/* Sentiment Summary */}
            <div className={styles.sentimentSummary}>
              <div className={styles.sentimentScore} style={{color: getSentimentColor(newsData.sentiment?.score || 0)}}>
                <span className={styles.sentimentValue}>
                  {getSentimentIcon(newsData.sentiment?.label)}
                  {newsData.sentiment?.label || 'NEUTRAL'}
                </span>
                <small>Score: {(newsData.sentiment?.score || 0).toFixed(2)}</small>
              </div>
              <div className={styles.sentimentBreakdown}>
                <span className={styles.bullishCount}>↑ {newsData.sentiment?.bullish_count || 0}</span>
                <span className={styles.bearishCount}>↓ {newsData.sentiment?.bearish_count || 0}</span>
                <span className={styles.neutralCount}>→ {newsData.sentiment?.neutral_count || 0}</span>
              </div>
            </div>
            
            {/* High Impact Alert */}
            {newsData.high_impact_events?.length > 0 && (
              <div className={styles.highImpactAlert}>
                <strong>🔴 HIGH IMPACT</strong>
                {newsData.high_impact_events.slice(0, 2).map((event, i) => (
                  <p key={i}>{event.substring(0, 80)}...</p>
                ))}
              </div>
            )}
            
            {/* Upcoming Events */}
            {newsData.upcoming_events?.length > 0 && (
              <div className={styles.upcomingEvents}>
                <strong>📅 Upcoming Events</strong>
                {newsData.upcoming_events.slice(0, 3).map((event, i) => (
                  <div key={i} className={styles.eventItem}>
                    <span className={styles.eventName}>{event.name}</span>
                    <span className={`${styles.eventImpact} ${styles[`impact${event.impact}`]}`}>
                      {event.impact}
                    </span>
                  </div>
                ))}
              </div>
            )}
            
            {/* Headlines */}
            <div className={styles.headlines}>
              <strong>Latest Headlines</strong>
              {newsData.headlines?.slice(0, 5).map((headline, i) => (
                <div key={i} className={styles.headlineItem}>
                  <span className={styles.headlineSource}>[{headline.source}]</span>
                  <span className={`${styles.headlineSentiment} ${styles[`sentiment${headline.sentiment}`]}`}>
                    {headline.sentiment === 'BULLISH' ? '↑' : headline.sentiment === 'BEARISH' ? '↓' : '→'}
                  </span>
                  <span className={styles.headlineText}>
                    {headline.is_high_impact && '🔴 '}
                    {headline.headline?.substring(0, 70)}...
                  </span>
                </div>
              ))}
            </div>
            
            {/* Risk Multiplier */}
            {newsData.risk_multiplier < 1 && (
              <div className={styles.riskMultiplier}>
                ⚠️ News Risk Adjustment: {(newsData.risk_multiplier * 100).toFixed(0)}%
              </div>
            )}
            
            {/* Stale Warning */}
            {newsData.stale && (
              <div className={styles.staleWarning}>
                ⚠️ News data is {newsData.minutes_old}m old
              </div>
            )}
          </div>
        )}
        
        {/* Show News Toggle */}
        {newsData?.available && !showNewsPanel && (
          <button 
            className={styles.showNewsButton}
            onClick={() => setShowNewsPanel(true)}
          >
            📰 Show News Panel
          </button>
        )}

        {/* Economic Calendar Section - Simple & Clean */}
        <div className={`${styles.card} ${styles.calendarCardSimple}`}>
          <div className={styles.calendarHeaderSimple}>
            <h3>📅 This Week's USD Events</h3>
            <button 
              className={styles.toggleButton}
              onClick={() => setShowCalendar(!showCalendar)}
            >
              {showCalendar ? 'Hide' : 'Show'}
            </button>
          </div>
          
          {showCalendar && (
            <div className={styles.calendarContainerSimple}>
              <p className={styles.calendarSubtitle}>🔴 High impact events can cause big moves in XAUUSD</p>
              {/* TradingView Light Theme - This Week Only */}
              <div style={{ height: '350px', width: '100%', borderRadius: '8px', overflow: 'hidden' }}>
                <iframe
                  src="https://s.tradingview.com/embed-widget/events/?locale=en#%7B%22colorTheme%22%3A%22light%22%2C%22isTransparent%22%3Atrue%2C%22width%22%3A%22100%25%22%2C%22height%22%3A%22100%25%22%2C%22importanceFilter%22%3A%221%2C2%22%2C%22countryFilter%22%3A%22us%22%7D"
                  title="USD Economic Events"
                  style={{ 
                    width: '100%', 
                    height: '100%', 
                    border: 'none'
                  }}
                  frameBorder="0"
                  allowTransparency="true"
                />
              </div>
            </div>
          )}
        </div>

        {/* System Status */}
        {systemStatus && (
          <div className={`${styles.card} ${styles.statusCard}`}>
            <h3>🖥️ System Status</h3>
            <div className={styles.statusGrid}>
              <div className={styles.statusItem}>
                <label>Models Loaded</label>
                <span>{systemStatus.health?.all_models_loaded ? "✅ All" : "⚠️ Partial"}</span>
              </div>
              <div className={styles.statusItem}>
                <label>Calibrators</label>
                <span>{systemStatus.health?.calibrators_loaded}/5</span>
              </div>
              <div className={styles.statusItem}>
                <label>Predictions</label>
                <span>{data?.prediction_count || 1}</span>
              </div>
              <div className={styles.statusItem}>
                <label>News</label>
                <span>{newsData?.available ? "✅ Active" : "⚠️ Unavailable"}</span>
              </div>
            </div>
          </div>
        )}

      </main>

      <footer className={styles.footer}>
         <p>
           Generated: {data?.generated_at} | 
           v{data?.system_version || '2.1'} |
           {liveMode ? " 🔴 Live" : " 📦 Batch"}
         </p>
      </footer>
    </div>
  );
}
