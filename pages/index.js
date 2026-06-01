/**
 * Gold Price Prediction Dashboard - Professional Forex Edition v4.0
 * Complete redesign as professional trading platform
 */

import { useState, useEffect } from "react";
import styles from "../styles/Home.module.css";

const REJECTION_MSG = {
  LOW_CONFIDENCE: "Low Confidence Score",
  HTF_CONFLICT: "Higher Timeframe Conflict",
  BAD_RR: "Insufficient Reward/Risk Ratio",
  HIGH_VOLATILITY: "Extreme Volatility (News/Crash)",
  RANGE_MARKET: "Market in Range (No Trend)",
  LOW_VOLATILITY: "Low Volatility (Dead Market)",
  REGIME_FILTER: "Market Regime Unfavorable",
  SL_TOO_TIGHT: "Stop Loss Too Tight",
  ZERO_RISK: "Zero Risk Allocation",
  LOT_CALC_ERROR: "Position Size Calculation Error",
  INSUFFICIENT_DATA: "Insufficient Market Data",
  HIGH_IMPACT_NEWS: "High-Impact News Event",
  CALENDAR_BLACKOUT: "Economic Calendar Blackout",
  EVENT_IMMINENT: "Major Economic Event Imminent",
  NEWS_NEGATIVE_SENTIMENT: "Strong Negative News Sentiment",
  CALIBRATION_UNSTABLE: "Calibration Drift Exceeds Safe Limit",
  CALIBRATION_WARNING: "Calibration Drift Warning",
};

const HTF_STATUS_LABELS = {
  ALIGNED: "✅ Aligned",
  SOFT_CONFLICT: "⚠️ Partial",
  HARD_CONFLICT: "❌ Conflict",
};

export default function Home() {
  const [data, setData] = useState(null);
  const [selectedTimeframe, setSelectedTimeframe] = useState("1h");
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [liveMode, setLiveMode] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(60);
  const [systemStatus, setSystemStatus] = useState(null);
  const [accountBalance, setAccountBalance] = useState(10000);
  const [riskPercentage, setRiskPercentage] = useState(1);
  const [newsData, setNewsData] = useState(null);

  const TIMEFRAMES = ["15m", "30m", "1h", "4h", "1d"];

  const fetchPrediction = async (showLoading = true) => {
    try {
      if (showLoading) setLoading(true);
      const res = await fetch(`/api/predict?t=${Date.now()}`);
      if (!res.ok) throw new Error("Failed to load predictions");
      const json = await res.json();
      setData(json);
      setLastUpdate(new Date());
      setError(null);
      setLiveMode(json.mode === "live");
    } catch (err) {
      console.error(err);
      setError("Failed to load prediction data.");
    } finally {
      setLoading(false);
    }
  };

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

  useEffect(() => {
    fetchPrediction(true);
    fetchStatus();
    fetchNews();
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    const predictionInterval = setInterval(() => {
      fetchPrediction(false);
    }, refreshInterval * 1000);
    const statusInterval = setInterval(fetchStatus, 30000);
    const newsInterval = setInterval(fetchNews, 60000);
    return () => {
      clearInterval(predictionInterval);
      clearInterval(statusInterval);
      clearInterval(newsInterval);
    };
  }, [autoRefresh, refreshInterval]);

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

  const getRejectionMessage = (code) => {
    if (!code) return "Unknown";
    return REJECTION_MSG[code] || code;
  };

  const getTimeSinceUpdate = () => {
    if (!lastUpdate) return "Never";
    const seconds = Math.floor((new Date() - lastUpdate) / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h`;
  };

  const currentTF = data?.predictions?.[selectedTimeframe];

  return (
    <div className={styles.containerPro}>
      {/* TOP NAVIGATION BAR */}
      <header className={styles.headerPro}>
        <div className={styles.headerLeft}>
          <h1>🥇 Gold Trader Pro</h1>
          <div className={styles.modeIndicator}>
            <span className={styles.liveIndicator}></span>
            {liveMode ? "🔴 LIVE" : "📦 BATCH"}
          </div>
        </div>
        <div className={styles.statusBadges}>
          <div className={styles.badge}>
            <span className={styles.badgeLabel}>Status:</span>
            <span className={styles.badgeValue}>{getTimeSinceUpdate()} ago</span>
          </div>
          <div className={styles.badge}>
            <span className={styles.badgeLabel}>Mode:</span>
            <span className={styles.badgeValue}>{liveMode ? "Live" : "Batch"}</span>
          </div>
        </div>
      </header>

      {/* MAIN TRADING FLOOR */}
      <div className={styles.mainPro}>
        {/* LEFT PANEL - MAIN ANALYSIS */}
        <div className={styles.leftPanelPro}>
          {/* CHART PLACEHOLDER */}
          <div className={styles.chartContainer}>
            <div className={styles.chartHeader}>
              <h2>XAUUSD - 1H</h2>
              <div className={styles.chartControls}>
                <span className={styles.priceDisplay}>
                  {currentTF?.current_price || "Loading..."} USD
                </span>
              </div>
            </div>
            <div className={styles.chartPlaceholder}>
              <div className={styles.chartGrid}>
                <svg width="100%" height="100%" style={{ opacity: 0.2 }}>
                  <defs>
                    <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                      <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#3b82f6" strokeWidth="0.5"/>
                    </pattern>
                  </defs>
                  <rect width="100%" height="100%" fill="url(#grid)" />
                </svg>
                <div style={{ position: 'absolute', bottom: '50%', left: '50%', transform: 'translate(-50%, 50%)', color: '#94a3b8', fontSize: '14px', textAlign: 'center' }}>
                  📈 Chart Integration Coming Soon
                </div>
              </div>
            </div>
          </div>

          {/* TIMEFRAME SELECTOR */}
          <div className={styles.timeframeNav}>
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf}
                onClick={() => setSelectedTimeframe(tf)}
                className={`${styles.tfButton} ${selectedTimeframe === tf ? styles.tfActive : ""}`}
              >
                {tf.toUpperCase()}
              </button>
            ))}
          </div>

          {/* MARKET DATA GRID */}
          <div className={styles.marketDataGrid}>
            <div className={styles.dataCard}>
              <label>Current Price</label>
              <div className={styles.dataValue}>${currentTF?.current_price || "N/A"}</div>
            </div>
            <div className={styles.dataCard}>
              <label>Regime</label>
              <div className={styles.dataValue}>{currentTF?.regime || "N/A"}</div>
            </div>
            <div className={styles.dataCard}>
              <label>Volatility</label>
              <div className={styles.dataValue}>{currentTF?.volatility_level || "N/A"}</div>
            </div>
            <div className={styles.dataCard}>
              <label>Trend Strength</label>
              <div className={styles.dataValue}>{currentTF?.trend_strength || "N/A"}</div>
            </div>
          </div>

          {/* TRADE DECISION BOX */}
          <div className={styles.decisionBox}>
            {loading ? (
              <div className={styles.loadingState}>
                <div className={styles.spinner}></div>
                <p>Analyzing market...</p>
              </div>
            ) : currentTF?.decision === "TRADE" ? (
              <div className={`${styles.tradeSignal} ${currentTF?.direction === "UP" ? styles.upSignal : styles.downSignal}`}>
                <div className={styles.directionBox}>
                  <div className={styles.arrow}>{currentTF?.direction === "UP" ? "📈" : "📉"}</div>
                  <div className={styles.directionText}>
                    <span className={styles.directionLabel}>{currentTF?.direction}</span>
                    <span className={styles.confidence}>
                      {currentTF?.confidence?.toFixed(1) || "0"}% Confidence
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className={styles.noTradeSignal}>
                <div className={styles.noTradeIcon}>⛔</div>
                <div className={styles.noTradeContent}>
                  <div className={styles.noTradeTitle}>NO TRADE</div>
                  <div className={styles.noTradeReason}>
                    {getRejectionMessage(currentTF?.rejection_reason)}
                  </div>
                  <div className={styles.noTradeDetails}>
                    {currentTF?.direction} {currentTF?.confidence?.toFixed(1)}% • Blocked by rules
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* MULTI-TIMEFRAME ANALYSIS */}
          <div className={styles.multiTimeframeBox}>
            <h3>Multi-Timeframe Analysis</h3>
            <div className={styles.mtfGrid}>
              {TIMEFRAMES.map((tf) => {
                const tfData = data?.predictions?.[tf];
                return (
                  <div key={tf} className={styles.mtfItem}>
                    <div className={styles.mtfTimeframe}>{tf.toUpperCase()}</div>
                    <div className={`${styles.mtfSignal} ${tfData?.decision === "TRADE" ? styles.tradeSignalSmall : styles.noTradeSmall}`}>
                      {tfData?.decision === "TRADE" ? (
                        <>
                          <span className={styles.mtfDirection}>{tfData?.direction}</span>
                          <span className={styles.mtfConfidence}>{tfData?.confidence?.toFixed(0)}%</span>
                        </>
                      ) : (
                        <>
                          <span>NO TRADE</span>
                          <span className={styles.mtfReason}>{tfData?.confidence?.toFixed(0)}%</span>
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* RIGHT SIDEBAR - CONTROLS & INFO */}
        <div className={styles.rightSidebarPro}>
          {/* TRADE SETUP CARD */}
          {currentTF?.decision === "TRADE" && currentTF?.setup && (
            <div className={styles.setupCard}>
              <h3>📍 Trade Setup</h3>
              <div className={styles.setupRow}>
                <span className={styles.setupLabel}>Entry</span>
                <span className={styles.setupValue}>${currentTF.setup.entry || "N/A"}</span>
              </div>
              <div className={styles.setupRow}>
                <span className={styles.setupLabel}>Stop Loss</span>
                <span className={styles.setupValue}>${currentTF.setup.stop_loss || "N/A"}</span>
              </div>
              <div className={styles.setupRow}>
                <span className={styles.setupLabel}>Take Profit</span>
                <span className={styles.setupValue}>${currentTF.setup.take_profit || "N/A"}</span>
              </div>
              <div className={styles.setupDivider}></div>
              <div className={styles.setupRow}>
                <span className={styles.setupLabel}>RR Ratio</span>
                <span className={styles.setupValue}>{currentTF.setup.rr_ratio?.toFixed(2) || "N/A"}</span>
              </div>
              <div className={styles.setupRow}>
                <span className={styles.setupLabel}>Position Size</span>
                <span className={styles.setupValue}>{calculatePositionSize(currentTF.setup)} Lots</span>
              </div>
            </div>
          )}

          {/* RISK MANAGEMENT PANEL */}
          <div className={styles.riskPanel}>
            <h3>💰 Risk Management</h3>
            <div className={styles.riskItem}>
              <label>Account Balance</label>
              <input
                type="number"
                value={accountBalance}
                onChange={(e) => setAccountBalance(Number(e.target.value))}
                className={styles.riskInput}
              />
            </div>
            <div className={styles.riskItem}>
              <label>Risk per Trade</label>
              <div className={styles.riskSliderContainer}>
                <input
                  type="range"
                  min="0.1"
                  max="5"
                  step="0.1"
                  value={riskPercentage}
                  onChange={(e) => setRiskPercentage(Number(e.target.value))}
                  className={styles.riskSlider}
                />
                <span className={styles.riskValue}>{riskPercentage.toFixed(1)}%</span>
              </div>
            </div>
            <div className={styles.riskInfo}>
              <div className={styles.riskInfoRow}>
                <span>Risk Amount:</span>
                <strong>${((accountBalance * riskPercentage) / 100).toFixed(2)}</strong>
              </div>
              <div className={styles.riskInfoRow}>
                <span>Account Risk:</span>
                <strong>{riskPercentage.toFixed(1)}%</strong>
              </div>
            </div>
          </div>

          {/* SYSTEM STATUS */}
          <div className={styles.statusPanel}>
            <h3>⚙️ System Status</h3>
            <div className={styles.statusItem}>
              <span>Mode</span>
              <strong>{liveMode ? "🔴 LIVE" : "📦 BATCH"}</strong>
            </div>
            <div className={styles.statusItem}>
              <span>Last Update</span>
              <strong>{getTimeSinceUpdate()}</strong>
            </div>
            <div className={styles.statusItem}>
              <span>Auto-Refresh</span>
              <strong>{autoRefresh ? `${refreshInterval}s` : "Off"}</strong>
            </div>
            {newsData && (
              <div className={styles.statusItem}>
                <span>News Status</span>
                <strong>{newsData.can_trade ? "✅ Clear" : "⛔ Blocked"}</strong>
              </div>
            )}
          </div>

          {/* CONTROL BUTTONS */}
          <div className={styles.controlButtons}>
            <label className={styles.checkboxLabel}>
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
              />
              Auto-Refresh
            </label>
            <select
              value={refreshInterval}
              onChange={(e) => setRefreshInterval(Number(e.target.value))}
              className={styles.refreshSelect}
              disabled={!autoRefresh}
            >
              <option value="30">30 seconds</option>
              <option value="60">1 minute</option>
              <option value="300">5 minutes</option>
              <option value="900">15 minutes</option>
            </select>
            <button onClick={handleBatchUpdate} className={styles.batchBtn} disabled={updating}>
              {updating ? "Updating..." : "📦 Batch Update"}
            </button>
            <button onClick={handleLiveUpdate} className={styles.liveBtn} disabled={updating}>
              {updating ? "Running..." : "🔴 Live Predict"}
            </button>
          </div>

          {/* ERROR DISPLAY */}
          {error && (
            <div className={styles.errorPanel}>
              <div className={styles.errorTitle}>⚠️ Error</div>
              <div className={styles.errorMessage}>{error}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
