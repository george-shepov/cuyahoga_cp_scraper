# Cuyahoga County Common Pleas Court Scraper

Automated web scraper for extracting case data from Cuyahoga County Common Pleas Court public records.

## Core Scripts

- **`main.py`** - Main scraper with PDF download capability
- **`download_sentencing_only.py`** - Download only sentencing entries (JE files) from all cases
- **`compare_versions.py`** - Compare different versions of the same case
- **`analyze_pdfs.py`** - Extract and analyze PDF metadata
- **`scan_brad_davis.py`** - Scan for Brad B Davis metadata pattern

## Usage

```bash
# Scrape cases without PDFs
python3 main.py scrape --year 2023 --start 684826 --limit 1

# Scrape with PDF downloads
python3 main.py scrape --year 2023 --start 684826 --limit 1 --download-pdfs

# Get statistics
python3 main.py stats --year 2023

# Compare case versions
python3 compare_versions.py CR-23-684826-A

# Analyze PDFs for a case
python3 analyze_pdfs.py CR-23-684826-A

# Scan for Brad B Davis metadata
python3 scan_brad_davis.py
```

## Directory Structure

```
.
├── main.py                      # Main scraper
├── download_sentencing_only.py  # Sentencing entry downloader
├── compare_versions.py          # Version comparison tool
├── analyze_pdfs.py              # PDF metadata analyzer
├── scan_brad_davis.py           # Brad Davis pattern scanner
├── requirements.txt             # Python dependencies
│
├── out/                         # Scraped JSON data
│   ├── 2023/                    # 9,339 cases
│   ├── 2024/                    # 203 cases
│   └── 2025/                    # 4,276 cases
│
├── docs/                        # Documentation
│   ├── analysis/                # Brad Davis investigation & analysis
│   ├── reports/                 # October 2025 analysis reports
│   ├── logs/                    # Download and scraping logs
│   ├── BACKOFF_STRATEGY.md
│   ├── COMPREHENSIVE_DATA_EXTRACTION_PLAN.md
│   ├── README_deploy.md
│   └── README_watchdog.md
│
├── scripts/                     # Utility scripts
├── deploy/                      # Deployment configs
├── logs/                        # Scraper runtime logs
└── _ARCHIVE/                    # Old scripts and documentation (73 files)
```

## Data Output

Each case is saved as JSON in `out/{year}/{case_id}.json` with:
- Case information
- Party details
- Docket entries (with PDF links if `--download-pdfs` used)
- Disposition
- Related cases
- Costs
- Attorneys

PDFs are saved to `out/{year}/{case_id}/` when using `--download-pdfs`.

## Requirements

```bash
pip install -r requirements.txt
```

Requires Python 3.8+ and Playwright for browser automation.

## Documentation

- **Brad Davis Investigation**: See `docs/analysis/BRAD_DAVIS_EVIDENCE_SUMMARY.md`
- **October 2025 Analysis**: See `docs/reports/`
- **Deployment**: See `docs/README_deploy.md`
- **Watchdog**: See `docs/README_watchdog.md`

## Notes

- The scraper includes extensive retry logic and backoff strategies
- Large dockets (90+ entries) have extended wait times for complete loading
- PDF metadata is automatically extracted when available
- Currently tracking 13,818 cases across 2023-2025
