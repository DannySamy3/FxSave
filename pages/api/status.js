/**
 * API Route: /api/status
 * 
 * Returns system status including:
 * - Last prediction time
 * - Data update status
 * - Model health
 * - Scheduler status
 */

import fs from "fs";
import path from "path";

export default function handler(req, res) {
  try {
    const publicDir = path.join(process.cwd(), "public");
    const pythonDir = path.join(process.cwd(), "python_model");
    const cacheDir = path.join(pythonDir, "cache");
    
    // Read prediction file
    const predictionPath = path.join(publicDir, "latest_prediction.json");
    let predictionStatus = null;
    
    if (fs.existsSync(predictionPath)) {
      const data = JSON.parse(fs.readFileSync(predictionPath, "utf-8"));
      predictionStatus = {
        generated_at: data.generated_at,
        system_version: data.system_version,
        mode: data.mode || "batch",
        prediction_count: data.prediction_count || 1,
        timeframes: Object.keys(data.predictions || {})
      };
    }
    
    // Check model files
    const timeframes = ["15m", "30m", "1h", "4h", "1d"];
    const modelStatus = {};
    
    timeframes.forEach(tf => {
      const modelPath = path.join(pythonDir, `xgb_${tf}.pkl`);
      const calibPath = path.join(pythonDir, `calibrator_${tf}.pkl`);
      
      modelStatus[tf] = {
        model_exists: fs.existsSync(modelPath),
        calibrator_exists: fs.existsSync(calibPath),
        model_size: fs.existsSync(modelPath) 
          ? (fs.statSync(modelPath).size / 1024 / 1024).toFixed(2) + " MB"
          : null
      };
    });
    
    // Check cache metadata
    let cacheStatus = null;
    const metadataPath = path.join(cacheDir, "metadata.json");
    
    if (fs.existsSync(metadataPath)) {
      try {
        cacheStatus = JSON.parse(fs.readFileSync(metadataPath, "utf-8"));
      } catch (e) {
        cacheStatus = { error: "Failed to read cache metadata" };
      }
    }
    
    // Build response
    const status = {
      timestamp: new Date().toISOString(),
      prediction: predictionStatus,
      models: modelStatus,
      cache: cacheStatus,
      health: {
        predictions_available: predictionStatus !== null,
        all_models_loaded: Object.values(modelStatus).every(m => m.model_exists),
        calibrators_loaded: Object.values(modelStatus).filter(m => m.calibrator_exists).length
      }
    };
    
    res.setHeader("Cache-Control", "no-store, max-age=0");
    res.status(200).json(status);
    
  } catch (error) {
    console.error("Status API error:", error);
    res.status(500).json({
      error: "Failed to get status",
      message: error.message
    });
  }
}






