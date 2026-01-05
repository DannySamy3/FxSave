# Complete System Startup - Web App + Auto-Trainer

## One Command to Start Everything!

Simply run:

```bash
d:\CODE\Gold-Trade\run_all.bat
```

Or double-click: `run_all.bat`

---

## What It Does

This single batch file starts **BOTH** services:

```
┌─────────────────────────────────────────────────┐
│           Main Control Window                   │
│  (Shows startup messages and status)            │
└─────────────────────────────────────────────────┘
         ↓                               ↓
┌──────────────────────┐    ┌──────────────────────┐
│  Next.js Web App     │    │  Auto-Trainer        │
│  Port 3000           │    │  Scheduler           │
│  http://localhost:3000│   │  5 PM Daily          │
└──────────────────────┘    └──────────────────────┘
```

---

## What Happens

### **Immediately:**

```
1. Main window opens showing startup messages
2. Window #1 opens: Next.js app starts on port 3000
3. Wait 3 seconds...
4. Window #2 opens: Auto-trainer scheduler starts
5. Both run continuously in parallel
```

### **Each Day at 5 PM:**

```
Auto-trainer automatically:
✅ Fetches new market data
✅ Retrains all models
✅ Compares with old models
✅ Deploys only if improvement found
✅ Logs results
```

---

## How to Use

### **Start Everything:**

Double-click `run_all.bat` or run:

```bash
d:\CODE\Gold-Trade\run_all.bat
```

### **Three Windows Will Open:**

1. **Main Window** (Control Center)
   - Shows startup messages
   - Status of both services
   - Keep this open to keep everything running

2. **Web App Window**
   - Title: "Gold Trade Web App - npm run dev"
   - Running on http://localhost:3000
   - Shows app logs

3. **Auto-Trainer Window**
   - Title: "Gold Trade Auto-Trainer - Daily Scheduler"
   - Running continuously
   - Shows training logs at 5 PM

---

## To Stop Everything

**Option 1: Close the main window**
- Closes the main control window
- Both services stop

**Option 2: Close individual windows**
- Close "Gold Trade Web App" window → App stops
- Close "Gold Trade Auto-Trainer" window → Scheduler stops

**Option 3: Manual stop**
```bash
# In each window, press Ctrl+C to stop
```

---

## Verification

Both are running if you see:

```
✅ WEB APP:         http://localhost:3000
✅ AUTO-TRAINER:    Waiting for 5 PM (17:00) daily
```

Test the web app: Open browser to `http://localhost:3000`

---

## Windows Task Scheduler (Optional Advanced Setup)

To make `run_all.bat` start automatically on computer boot:

1. Press `Windows + R` → type `taskschd.msc` → Enter
2. Click **Create Basic Task**
3. Fill in:
   - **Name:** "Gold Trade Full System"
   - **Trigger:** At startup
   - **Action:** Start program → Select `run_all.bat`
4. Click **OK**

Now both services start automatically when you boot! 

---

## Troubleshooting

### **Web app not starting:**
```
Check if port 3000 is already in use
Run: netstat -ano | findstr :3000
If yes, close the other process or use different port
```

### **Scheduler not starting:**
```
Check if Python is installed
Run: python --version
Check if schedule module is installed
Run: pip install schedule
```

### **Both showing but nothing happening:**
```
Wait 30 seconds for Next.js to fully compile
Check web app logs in its window
Check scheduler logs in its window
```

---

## File Locations

```
run_all.bat
├── npm run dev
│   └── Next.js app (d:\CODE\Gold-Trade)
│       └── Port 3000
│
└── python daily_scheduler.py
    └── Auto-trainer (d:\CODE\Gold-Trade\python_model)
        └── Runs at 5 PM daily
```

---

## Logs

Check what's happening:

```bash
# Web app logs (shown in its window)
# Auto-trainer logs:
type d:\CODE\Gold-Trade\python_model\daily_training.log
type d:\CODE\Gold-Trade\python_model\scheduler.log
```

---

## Summary

**One simple command starts your complete trading system:**

✅ Web app (for viewing predictions)
✅ Auto-trainer (for daily model improvement)
✅ Both run in parallel
✅ Completely automated

**Just double-click `run_all.bat` and you're done!** 🚀

