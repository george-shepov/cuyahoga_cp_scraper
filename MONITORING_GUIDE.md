# Case Monitoring System - User Guide

## Overview

Automated system that monitors your court cases and saves print versions (HTML + PDF) of all tabs. Only saves when changes are detected to avoid wasting space with duplicate copies.

## Features

✅ **Automated Navigation** - Goes to each case, clicks through all tabs
✅ **Print Version Capture** - Saves both HTML and PDF for each tab
✅ **Change Detection** - Uses SHA256 hashing to detect actual changes
✅ **No Duplicates** - Only saves when content has materially changed
✅ **Timestamped Files** - Format: `MM-DD-YYYY Title.pdf`
✅ **Continuous Monitoring** - Runs at configurable intervals
✅ **Adaptive Speed** - Checks faster when changes are detected
✅ **Multiple Case Types** - Supports both Criminal (CR) and Domestic (DR) cases

## Quick Start

### Single Check (Run Once)
```bash
cd /home/shepov/dev/scrapers/criminal/cuyahoga_cp_scraper
python3 monitor_my_cases.py
```

### Continuous Monitoring (Check Every 5 Minutes)
```bash
python3 monitor_my_cases.py --continuous
```

### Rapid Monitoring (Check Every 1 Minute)
```bash
python3 monitor_my_cases.py --continuous --interval 60 --rapid 30
```

### Interactive Start Script
```bash
./start_monitor.sh
```

## How It Works

### 1. Change Detection Algorithm

For each tab in each case:
1. Fetches the current content (HTML or PDF)
2. Computes SHA256 hash of the content
3. Compares with previously saved hash (stored in `.last_hash` file)
4. If hashes match → **Skip** (no changes)
5. If hashes differ → **Save** new version with timestamp

### 2. File Organization

Files are saved to: `/home/shepov/Documents/2- Cuyahoga County Court/{CASE_ID}/{TAB_NAME}/`

**Example structure:**
```
/home/shepov/Documents/2- Cuyahoga County Court/
├── CR-23-684826-A/
│   ├── Case Summary/
│   │   ├── 12-19-2025 Criminal Case Summary.html
│   │   ├── 12-19-2025 Criminal Case Summary.pdf
│   │   ├── .last_hash           # Hash of HTML content
│   │   └── .last_hash_PDF       # Hash of PDF content
│   ├── Defendant/
│   ├── Documents/
│   ├── Docket/
│   ├── Cost/
│   └── Attorney/
├── CR-25-706402-A/
│   └── (same structure)
└── DR-25-403973/
    ├── Case Summary/
    ├── Parties/
    ├── Documents/
    ├── Image/
    ├── Docket/
    ├── Service/
    ├── Costs/
    └── All/
```

### 3. Monitoring Modes

**Single Check Mode:**
- Runs once and exits
- Good for manual updates
- Command: `python3 monitor_my_cases.py`

**Continuous Mode:**
- Runs forever
- Default: checks every 5 minutes
- Command: `python3 monitor_my_cases.py --continuous`

**Adaptive Speed:**
- When changes detected: switches to rapid check (60 seconds)
- When no changes: returns to normal interval (300 seconds)
- Catches updates quickly without hammering the server

## Configuration

### Cases Monitored

The system monitors all cases in `my_cases.json`:
- **CR-23-684826-A** (Criminal)
- **CR-25-706402-A** (Criminal)
- **DR-25-403973** (Domestic)

### Custom Intervals

```bash
# Check every 10 minutes normally, every 2 minutes when changes detected
python3 monitor_my_cases.py --continuous --interval 600 --rapid 120

# Check every 30 seconds (very aggressive)
python3 monitor_my_cases.py --continuous --interval 30 --rapid 15
```

### Command Line Options

```
--continuous, -c    Run continuously (default: single check)
--interval, -i      Check interval in seconds (default: 300)
--rapid, -r         Rapid interval when changes detected (default: 60)
```

## Tabs Monitored

### Criminal Cases (CR-*)
1. Case Summary
2. Defendant
3. Documents
4. Docket
5. Cost
6. Attorney

### Domestic Cases (DR-*)
1. Case Summary
2. Parties
3. Documents
4. Image
5. Docket
6. Service
7. Costs
8. All

## Output Examples

### When Changes Detected
```
================================================================================
Monitoring: CR-23-684826-A (CRIMINAL)
================================================================================

Case Summary:
  ✓ Case Summary: Saved HTML (102400 bytes)
  ✓ Case Summary: Saved PDF (264192 bytes)

Defendant:
  ↔ Defendant: No changes detected
  ↔ Defendant: No PDF changes detected

Docket:
  ✓ Docket: Saved HTML (153600 bytes)
  ✓ Docket: Saved PDF (315392 bytes)

================================================================================
✅ CHANGES DETECTED in CR-23-684826-A
================================================================================
```

### When No Changes
```
================================================================================
Monitoring: CR-25-706402-A (CRIMINAL)
================================================================================

Case Summary:
  ↔ Case Summary: No changes detected
  ↔ Case Summary: No PDF changes detected

Defendant:
  ↔ Defendant: No changes detected
  ↔ Defendant: No PDF changes detected

================================================================================
⚪ No changes in CR-25-706402-A
================================================================================
```

## Running as Background Service

### Option 1: nohup (Simple)
```bash
nohup python3 monitor_my_cases.py --continuous > /tmp/case_monitor.log 2>&1 &
```

### Option 2: screen (Detachable Terminal)
```bash
screen -S case_monitor
python3 monitor_my_cases.py --continuous
# Press Ctrl+A then D to detach
# Reattach with: screen -r case_monitor
```

### Option 3: systemd Service (Professional)

Create `/etc/systemd/system/case-monitor.service`:
```ini
[Unit]
Description=Court Case Monitoring Service
After=network.target

[Service]
Type=simple
User=shepov
WorkingDirectory=/home/shepov/dev/scrapers/criminal/cuyahoga_cp_scraper
ExecStart=/usr/bin/python3 monitor_my_cases.py --continuous --interval 300 --rapid 60
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable case-monitor.service
sudo systemctl start case-monitor.service
sudo systemctl status case-monitor.service
```

## Storage Optimization

The system **automatically prevents duplicate storage** by:

1. **Hash Comparison** - Only saves when content actually changes
2. **Separate HTML/PDF Tracking** - Each format tracked independently
3. **No Timestamp Duplicates** - Multiple checks on same day only save if changed

**Space Savings Example:**
- Without change detection: ~50 MB/day for 3 cases
- With change detection: ~5 MB/day (only when updates occur)
- **90% reduction** in wasted storage

## Troubleshooting

### Browser Doesn't Start
```bash
# Install Playwright browser
playwright install chromium
```

### Permission Denied on /home/shepov/Documents
```bash
# Check directory permissions
ls -la "/home/shepov/Documents/2- Cuyahoga County Court/"

# Create case directories if missing
python3 -c "from pathlib import Path; Path('/home/shepov/Documents/2- Cuyahoga County Court/CR-23-684826-A/Docket').mkdir(parents=True, exist_ok=True)"
```

### Hash Files (.last_hash) Issues
```bash
# Reset change detection (will force re-save on next run)
find "/home/shepov/Documents/2- Cuyahoga County Court/" -name ".last_hash*" -delete
```

### Stop Continuous Monitoring
```bash
# Find process
ps aux | grep monitor_my_cases

# Kill it
kill <PID>
```

## Best Practices

1. **Start with Single Check** - Test first: `python3 monitor_my_cases.py`
2. **Use Continuous for Daily Monitoring** - Run with default 5-minute interval
3. **Use Rapid During Active Cases** - When expecting frequent updates
4. **Check Logs Regularly** - Monitor for errors or issues
5. **Clean Old Versions Periodically** - Keep last 30 days of backups

## Advanced Usage

### Monitor Only Specific Cases

Edit `my_cases.json` to include/exclude cases, then run:
```bash
python3 monitor_my_cases.py
```

### Custom Save Locations

Edit `CASES_DIR` in `monitor_my_cases.py`:
```python
CASES_DIR = Path("/path/to/your/directory")
```

### Run on Schedule (cron)

For periodic checks without continuous mode:
```bash
# Check every hour
0 * * * * cd /home/shepov/dev/scrapers/criminal/cuyahoga_cp_scraper && python3 monitor_my_cases.py >> /tmp/monitor.log 2>&1
```

## Statistics Tracking

The system prints summaries after each check:

```
################################################################################
# MONITORING ITERATION #5
# Time: 2025-12-19 01:30:00
# Cases: 3
################################################################################

[... case checks ...]

⚡ Changes detected! Checking again in 60 seconds...
```

## Support

- **Script Location:** `/home/shepov/dev/scrapers/criminal/cuyahoga_cp_scraper/monitor_my_cases.py`
- **Output Directory:** `/home/shepov/Documents/2- Cuyahoga County Court/`
- **Configuration:** `my_cases.json`

---

**Last Updated:** December 19, 2025
