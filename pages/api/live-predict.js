/**
 * API Route: /api/live-predict
 * 
 * Triggers a live prediction cycle using incremental data.
 * Uses the Python live_predictor module.
 * 
 * POST /api/live-predict
 * Returns: { success, output, predictions }
 */

import { exec } from "child_process";
import path from "path";
import fs from "fs";

export default function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ message: "Method not allowed" });
  }

  // Path to the live predictor script
  const scriptPath = path.resolve(
    process.cwd(),
    "python_model",
    "live_predictor.py"
  );

  // Python command
  const pythonCommand =
    process.platform === "win32"
      ? "C:\\Users\\Developer\\AppData\\Local\\Programs\\Python\\Python312\\python.exe"
      : "python3";

  const command = `"${pythonCommand}" "${scriptPath}"`;

  console.log(`Executing live prediction: ${command}`);

  exec(
    command,
    {
      cwd: path.dirname(scriptPath),
      env: { ...process.env, PYTHONIOENCODING: "utf-8" },
      timeout: 120000, // 2 minute timeout
    },
    (error, stdout, stderr) => {
      if (error) {
        console.error(`Exec error: ${error}`);
        console.error(`Stderr: ${stderr}`);
        return res.status(500).json({
          success: false,
          message: "Live prediction failed",
          error: error.message,
          details: stderr,
        });
      }

      console.log(`Stdout: ${stdout}`);
      if (stderr) console.warn(`Stderr warning: ${stderr}`);

      // Read the generated predictions
      const predictionPath = path.join(
        process.cwd(),
        "public",
        "latest_prediction.json"
      );

      let predictions = null;
      if (fs.existsSync(predictionPath)) {
        try {
          predictions = JSON.parse(fs.readFileSync(predictionPath, "utf-8"));
        } catch (e) {
          console.error("Failed to read predictions:", e);
        }
      }

      return res.status(200).json({
        success: true,
        message: "Live prediction completed",
        output: stdout,
        predictions: predictions,
      });
    }
  );
}






