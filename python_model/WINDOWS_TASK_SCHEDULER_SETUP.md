# Windows Task Scheduler Setup Guide

**System**: Gold-Trade Pro v2.2.0  
**Platform**: Windows  
**Tasks**: Daily CSV Update + Model Learning

---

## Quick Setup (5 Minutes)

### Step 1: Create Task for Daily Updates

1. **Open Task Scheduler**
   - Press `Win + R`, type `taskschd.msc`, press Enter
   - Or search "Task Scheduler" in Start menu

2. **Create Basic Task**
   - Click "Create Basic Task" in right panel
   - Name: `Gold-Trade Daily Updates`
   - Description: `Daily CSV update and model learning after market close`

3. **Set Trigger**
   - Trigger: `Daily`
   - Start date: Today's date
   - Time: `6:00 PM` (18:00)
   - Recur every: `1 days`
   - ✅ Check "Monday through Friday only" (if available)

4. **Set Action**
   - Action: `Start a program`
   - Program/script: `python`
   - Add arguments: `D:\CODE\Gold-Trade\python_model\run_daily_updates.py`
   - Start in: `D:\CODE\Gold-Trade\python_model`

5. **Finish**
   - ✅ Check "Open the Properties dialog for this task"
   - Click "Finish"

6. **Configure Advanced Settings**
   - **General Tab**:
     - ✅ Run whether user is logged on or not
     - ✅ Run with highest privileges
     - Configure for: `Windows 10` (or your version)
   
   - **Conditions Tab**:
     - ✅ Uncheck "Start the task only if the computer is on AC power"
     - ✅ Check "Wake the computer to run this task" (optional)
   
   - **Settings Tab**:
     - ✅ Allow task to be run on demand
     - ✅ Run task as soon as possible after a scheduled start is missed
     - ✅ If the task fails, restart every: `10 minutes`
     - Attempt to restart up to: `3 times`
     - ✅ Stop the task if it runs longer than: `2 hours`
   
   - **Actions Tab**:
     - Verify the action is correct
     - Optional: Add "On failure" action to send email (requires SMTP config)
   
   - **History Tab**:
     - ✅ Enable "Enable All Tasks History" (for monitoring)

7. **Click OK** to save

---

## Step 2: Test the Task

### Manual Test

1. **Right-click** the task in Task Scheduler
2. Select **"Run"**
3. Wait for execution
4. Check **"History"** tab for results

### Verify Execution

1. Check Python log files:
   ```
   D:\CODE\Gold-Trade\python_model\logs\csv_update_log.json
   D:\CODE\Gold-Trade\python_model\logs\model_learning_log.json
   ```

2. Check Windows Event Viewer:
   - Open Event Viewer
   - Navigate to: `Windows Logs` → `Application`
   - Look for entries from "Task Scheduler"

3. Verify files updated:
   - Check `gold_data.csv` for new rows
   - Check model files (`xgb_*.pkl`) modification dates

---

## Step 3: Configure Email Alerts (Optional)

### Option A: Task Scheduler Email (Simple)

1. **Edit Task** → **Actions** tab
2. Click **"New"** → Select **"Send an e-mail"**
3. Configure:
   - From: `your-email@example.com`
   - To: `your-email@example.com`
   - Subject: `Gold-Trade Daily Update Failed`
   - Text: `The daily update task failed. Check logs for details.`
4. Set trigger: **"On failure"**

**Note**: Requires SMTP server configuration (may not work with all email providers).

### Option B: PowerShell Script (Recommended)

Create `send_alert.ps1`:
```powershell
# send_alert.ps1
param(
    [string]$Subject = "Gold-Trade Update Alert",
    [string]$Body = "Check logs for details."
)

$SMTPServer = "smtp.gmail.com"
$SMTPPort = 587
$Username = "your-email@gmail.com"
$Password = "your-app-password"

$From = "your-email@gmail.com"
$To = "your-email@gmail.com"

$Message = New-Object System.Net.Mail.MailMessage($From, $To)
$Message.Subject = $Subject
$Message.Body = $Body

$SMTP = New-Object System.Net.Mail.SmtpClient($SMTPServer, $SMTPPort)
$SMTP.EnableSsl = $true
$SMTP.Credentials = New-Object System.Net.NetworkCredential($Username, $Password)

$SMTP.Send($Message)
```

Add to task as "On failure" action:
- Program: `powershell.exe`
- Arguments: `-File "D:\CODE\Gold-Trade\python_model\send_alert.ps1" -Subject "Update Failed"`

---

## Step 4: Monitoring Setup

### Daily Check Script

Create `check_daily_updates.ps1`:
```powershell
# check_daily_updates.ps1
$logDir = "D:\CODE\Gold-Trade\python_model\logs"

# Check last CSV update
$csvLog = Get-Content "$logDir\csv_update_log.json" | ConvertFrom-Json
$lastCsv = $csvLog[-1]

$modelLog = Get-Content "$logDir\model_learning_log.json" | ConvertFrom-Json
$lastModel = $modelLog[-1]

Write-Host "Last CSV Update: $($lastCsv.timestamp) - Status: $($lastCsv.status)"
Write-Host "Last Model Learning: $($lastModel.timestamp) - Status: $($lastModel.status)"

if ($lastCsv.status -eq "failed" -or $lastModel.status -eq "failed") {
    Write-Host "WARNING: Recent failures detected!" -ForegroundColor Red
}
```

Run daily: `powershell -File check_daily_updates.ps1`

---

## Troubleshooting

### Task Not Running

1. **Check Task Status**:
   - Open Task Scheduler
   - Find your task
   - Check "Last Run Result" (should be `0x0` for success)

2. **Check Python Path**:
   - Verify `python` is in system PATH
   - Or use full path: `C:\Python312\python.exe`

3. **Check Permissions**:
   - Task must run as user with write permissions
   - Or run as Administrator

4. **Check Logs**:
   - Windows Event Viewer → Application log
   - Look for errors from Task Scheduler

### Task Fails Immediately

1. **Test Script Manually**:
   ```cmd
   cd D:\CODE\Gold-Trade\python_model
   python run_daily_updates.py
   ```

2. **Check Dependencies**:
   - Ensure all Python packages installed
   - Check `requirements.txt`

3. **Check File Paths**:
   - Verify all paths in script are correct
   - Check `gold_data.csv` is writable

### Task Runs But No Updates

1. **Check Log Files**:
   - Review `logs/csv_update_log.json`
   - Check for "skipped" status

2. **Check Market Hours**:
   - Updates only run on trading days
   - Weekend/holiday updates may be skipped

3. **Check Data Availability**:
   - Verify Yahoo Finance data is available
   - Check internet connection

---

## Advanced Configuration

### Multiple Timeframes

Create separate tasks for different timeframes:
- Task 1: `Gold-Trade Daily Update (1d)` - 6:00 PM
- Task 2: `Gold-Trade Hourly Update (1h)` - Every hour during market hours

### Conditional Execution

Use PowerShell script to check conditions:
```powershell
# check_market_open.ps1
$day = (Get-Date).DayOfWeek
if ($day -eq "Saturday" -or $day -eq "Sunday") {
    exit 1  # Skip on weekends
}
exit 0  # Run on weekdays
```

Add as condition in Task Scheduler → Conditions → Start task only if following network connection is available.

### Backup Before Updates

Add pre-action to backup files:
- Program: `powershell.exe`
- Arguments: `-Command "Copy-Item 'D:\CODE\Gold-Trade\python_model\gold_data.csv' 'D:\CODE\Gold-Trade\python_model\backups\gold_data_$(Get-Date -Format 'yyyyMMdd').csv'"`

---

## Maintenance

### Weekly Checks

1. **Review Task History**:
   - Task Scheduler → History tab
   - Check for failures

2. **Review Log Files**:
   - Check `logs/csv_update_log.json`
   - Check `logs/model_learning_log.json`

3. **Verify Data**:
   - Check `gold_data.csv` has recent data
   - Verify model files are updated

### Monthly Maintenance

1. **Clean Old Logs**:
   - Keep last 1000 entries in log files
   - Archive older logs

2. **Verify Task Schedule**:
   - Check task is still enabled
   - Verify trigger times are correct

3. **Test Manual Run**:
   - Right-click task → Run
   - Verify execution succeeds

---

## Summary

✅ **Task Created**: `Gold-Trade Daily Updates`  
✅ **Schedule**: Daily at 6:00 PM (Monday-Friday)  
✅ **Action**: Runs `run_daily_updates.py`  
✅ **Monitoring**: Check logs and Event Viewer  
✅ **Alerts**: Configure email on failure (optional)

**Next Steps**:
1. Test task manually
2. Monitor for 1 week
3. Configure alerts if needed
4. Set up weekly maintenance routine

---

## Quick Reference

**Task Name**: `Gold-Trade Daily Updates`  
**Trigger**: Daily at 6:00 PM  
**Program**: `python`  
**Arguments**: `D:\CODE\Gold-Trade\python_model\run_daily_updates.py`  
**Start In**: `D:\CODE\Gold-Trade\python_model`  
**Run As**: Your user account (or Administrator)  
**Log Files**: `python_model/logs/*.json`

