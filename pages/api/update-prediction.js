import { exec } from 'child_process';
import path from 'path';

export default function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ message: 'Method not allowed' });
  }

  // Resolve path to the python script
  // pages/api/update-prediction.js -> ../../python_model/predict.py
  const scriptPath = path.resolve(process.cwd(), 'python_model', 'predict.py');
  
  // Use absolute path to Python since we know where it is
  const pythonCommand = 'C:\\Users\\Developer\\AppData\\Local\\Programs\\Python\\Python312\\python.exe';

  // Double quotes around paths to handle spaces
  const command = `"${pythonCommand}" "${scriptPath}"`;

  console.log(`Executing: ${command}`);

  exec(command, { 
    cwd: path.dirname(scriptPath),
    env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
  }, (error, stdout, stderr) => {
    if (error) {
      console.error(`Exec error: ${error}`);
      console.error(`Stderr: ${stderr}`);
      return res.status(500).json({ 
        message: 'Failed to generate prediction', 
        error: error.message,
        details: stderr 
      });
    }

    console.log(`Stdout: ${stdout}`);
    if (stderr) console.error(`Stderr warning: ${stderr}`);

    // The script generates a file, so we just return success
    return res.status(200).json({ 
      message: 'Prediction generated successfully',
      output: stdout
    });
  });
}
