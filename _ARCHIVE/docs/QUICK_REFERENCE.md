# Quick Reference - Court Case Scraping

## 🎯 What Do You Want to Do?

### 1. Get Latest Data for My Cases (JSON + PDFs)
```bash
cd /home/shepov/dev/scrapers/criminal/cuyahoga_cp_scraper
python3 scrape_my_cases.py
```
**Output:** `out/2023/`, `out/2025/` (JSON files + PDFs)

### 2. Monitor Cases for Changes (HTML + PDF Print Versions)
```bash
# Single check
python3 monitor_my_cases.py

# Continuous monitoring (every 5 min)
python3 monitor_my_cases.py --continuous

# Interactive menu
./start_monitor.sh
```
**Output:** `/home/shepov/Documents/2- Cuyahoga County Court/{CASE_ID}/{TAB}/`

### 3. Do Both (Recommended)

**Terminal 1:** Data scraping
```bash
python3 scrape_my_cases.py
```

**Terminal 2:** Print version monitoring
```bash
python3 monitor_my_cases.py --continuous
```

## 📂 Where's My Data?

### Structured JSON Data + PDFs
```
/home/shepov/dev/scrapers/criminal/cuyahoga_cp_scraper/out/
├── 2023/
│   ├── 2023-684826_TIMESTAMP.json
│   └── pdfs/CR-23-684826-A/
└── 2025/
    ├── 2025-706402_TIMESTAMP.json
    └── pdfs/CR-25-706402-A/
```

### Print Versions (HTML + PDF)
```
/home/shepov/Documents/2- Cuyahoga County Court/
├── CR-23-684826-A/
│   ├── Docket/
│   │   ├── 12-19-2025 Criminal Case Docket Page.html
│   │   ├── 12-19-2025 Criminal Case Docket Page.pdf
│   │   └── .last_hash
│   ├── Case Summary/
│   ├── Defendant/
│   └── ...
├── CR-25-706402-A/
└── DR-25-403973/
```

## ⚙️ Your Cases

- **CR-23-684826-A** (Criminal 2023)
- **CR-25-706402-A** (Criminal 2025)
- **DR-25-403973** (Domestic 2025)

Edit `/home/shepov/dev/scrapers/criminal/cuyahoga_cp_scraper/my_cases.json` to add more.

## 🔧 Common Commands

```bash
# Location
cd /home/shepov/dev/scrapers/criminal/cuyahoga_cp_scraper

# One-time data scrape
python3 scrape_my_cases.py

# Monitor for changes (single check)
python3 monitor_my_cases.py

# Continuous monitoring (5 min interval)
python3 monitor_my_cases.py --continuous

# Rapid monitoring (1 min interval)
python3 monitor_my_cases.py --continuous --interval 60

# Background monitoring
nohup python3 monitor_my_cases.py --continuous > /tmp/monitor.log 2>&1 &

# Stop background monitoring
pkill -f monitor_my_cases

# View monitoring logs
tail -f /tmp/monitor.log
```

## 🎨 Output Examples

### Data Scraper
```
✓ Successfully scraped CR-23-684826-A
  - 96 docket entries
  - 18 PDFs downloaded
  - Saved: out/2023/2023-684826_20251219_053849.json
```

### Monitor (Changes Detected)
```
Docket:
  ✓ Docket: Saved HTML (153600 bytes)
  ✓ Docket: Saved PDF (315392 bytes)
✅ CHANGES DETECTED in CR-23-684826-A
```

### Monitor (No Changes)
```
Docket:
  ↔ Docket: No changes detected
  ↔ Docket: No PDF changes detected
⚪ No changes in CR-25-706402-A
```

## 💡 Tips

1. **Run data scraper when you need latest JSON/PDFs**
2. **Run monitor continuously to catch updates as they happen**
3. **Monitor only saves when content actually changes** (no duplicates!)
4. **Check faster when changes detected** (adaptive speed)
5. **All automated - set it and forget it**

## 📚 Documentation

- **Data Scraper:** `README.md`, `CLAUDE.md`
- **Monitor:** `MONITORING_GUIDE.md`
- **Setup:** `SETUP_SUMMARY.md`, `SUCCESS_REPORT.md`

---
**Location:** `/home/shepov/dev/scrapers/criminal/cuyahoga_cp_scraper/`
