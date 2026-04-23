# Cuyahoga County Common Pleas Court Scraper & Analytics

Automated web scraper for extracting case data from Cuyahoga County Common Pleas Court public records, with **AI-powered analytics** and **attorney recommendation engine**.

## 🆕 New Features

### **Attorney Recommendation System** 🎯
Answer the critical question: **"Given the judge and prosecutor assigned to my case, which attorney should I hire?"**

- **Smart Recommendations**: ML-based attorney ranking using historical matchup data
- **Judge Analytics**: Track conviction rates, sentencing patterns, defendant favorability
- **Prosecutor Analytics**: Win rates, aggressiveness scores, trial performance
- **Defense Attorney Analytics**: Win rates by judge/prosecutor, effectiveness scores
- **Matchup Analysis**: Detailed analysis of judge-prosecutor combinations with difficulty levels
- **Document Analysis**: AI-powered PDF analysis of court documents
- **Quadrant Analysis**: Multi-dimensional case categorization (Severity vs. Complexity, Speed vs. Outcome, Cost vs. Representation)

### **Technology Stack**
- **Databases**: PostgreSQL (analytics) + MongoDB (raw data)
- **LLM Integration**: Ollama (local), OpenAI, Anthropic, Groq
- **API**: FastAPI REST API with Swagger docs
- **Deployment**: Docker Compose with 7 services

📚 **[Read the Analytics Guide](docs/ANALYTICS_GUIDE.md)** | **[Implementation Summary](docs/IMPLEMENTATION_SUMMARY.md)**

## Core Scripts

- **`main.py`** - Main scraper with PDF download capability
- **`scrape_my_cases.py`** - 🆕 **Automated scraper for your specific cases** (CR-23-684826-A, CR-25-706402-A)
- **`monitor_my_cases.py`** - 🆕 **Continuous monitor that saves print versions when changes detected** (no duplicates!)
- **`download_sentencing_only.py`** - Download only sentencing entries (JE files) from all cases
- **`repair_incomplete_cases.py`** - Multi-threaded repair system for incomplete/broken JSONs
- **`compare_versions.py`** - Compare different versions of the same case
- **`analyze_pdfs.py`** - Extract and analyze PDF metadata
- **`scan_brad_davis.py`** - Scan for Brad B Davis metadata pattern

## Usage

```bash
# Scrape with auto-detected year (searches case number to find year)
python3 main.py scrape --start 678533 --limit 1

# Scrape cases with specified year
python3 main.py scrape --year 2023 --start 678533 --limit 1

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

# Repair incomplete/broken cases (multi-threaded, one thread per year)
python3 repair_incomplete_cases.py
```

## Cloud Or Hybrid Worker Deployment

If you want scraping off your laptop, run three dedicated workers on a VPS:

1. Forward miner: continuously mines newer case numbers.
2. Backward miner: continuously mines older history.
3. Targeted worker: continuously refreshes specific case IDs (for example your own active matters).

### New Worker Files

- `scripts/cloud_range_worker.py`: persistent forward or backward numeric miner using a cursor file.
- `scripts/cloud_targeted_worker.py`: periodic targeted refresh based on `my_cases.json`.
- `deploy/docker-compose.workers.yml`: 3-worker VPS stack.

### VPS Quick Start

```bash
# 1) Copy repo to VPS
git clone <your-repo-url> cuyahoga_cp_scraper
cd cuyahoga_cp_scraper

# 2) Start workers
docker-compose -f deploy/docker-compose.workers.yml up -d --build

# 3) Watch logs
docker-compose -f deploy/docker-compose.workers.yml logs -f scraper-forward
docker-compose -f deploy/docker-compose.workers.yml logs -f scraper-backward
docker-compose -f deploy/docker-compose.workers.yml logs -f scraper-targeted
```

### Hybrid Mode

- VPS runs the heavy miners (`scraper-forward`, `scraper-backward`).
- Your local machine runs only analytics, review, or one-off scrape/repair commands.
- Keep shared output in object storage (S3/Backblaze) or rsync it nightly:

```bash
rsync -az --delete user@your-vps:/path/to/cuyahoga_cp_scraper/out/ ./out/
```

### Adjusting Worker Strategy

- Change `--start`, `--limit`, and `--workers` in `deploy/docker-compose.workers.yml`.
- Backward floor is set by `--min-case`.
- Targeted cases come from `my_cases.json` (`cases[].case_id`).
- Cursor state is persisted in `cloud_state/forward.cursor` and `cloud_state/backward.cursor`.

## Directory Structure

```text
.
├── main.py                      # Main scraper
├── download_sentencing_only.py  # Sentencing entry downloader
├── compare_versions.py          # Version comparison tool
├── analyze_pdfs.py              # PDF metadata analyzer
├── scan_brad_davis.py           # Brad Davis pattern scanner
├── requirements.txt             # Python dependencies
│
├── api/                         # 🆕 FastAPI REST API
│   └── main.py                  # API endpoints
│
├── database/                    # 🆕 Database models
│   ├── models_postgres.py       # PostgreSQL schema
│   ├── models_mongo.py          # MongoDB schema
│   └── analytics_models.py      # Analytics tables
│
├── services/                    # 🆕 Business logic
│   ├── attorney_recommender.py  # Attorney recommendation engine
│   ├── analytics_calculator.py  # Performance metrics calculator
│   ├── quadrant_analyzer.py     # Quadrant analysis system
│   ├── llm_service.py           # LLM integration (Ollama, OpenAI, etc.)
│   └── document_analyzer.py     # PDF document analysis
│
├── out/                         # Scraped JSON data
│   ├── 2023/                    # 9,339 cases
│   ├── 2024/                    # 203 cases
│   └── 2025/                    # 4,276 cases
│
├── docs/                        # Documentation
│   ├── ANALYTICS_GUIDE.md       # 🆕 Analytics user guide
│   ├── IMPLEMENTATION_SUMMARY.md # 🆕 Implementation details
│   ├── ARCHITECTURE_ENHANCEMENT_PLAN.md # 🆕 Architecture design
│   ├── analysis/                # Brad Davis investigation & analysis
│   ├── reports/                 # October 2025 analysis reports
│   └── logs/                    # Download and scraping logs
│
├── scripts/                     # Utility scripts
│   ├── setup_analytics.sh       # 🆕 Setup automation
│   ├── import_existing_data.py  # 🆕 Data import
│   └── calculate_analytics.py   # 🆕 Analytics calculation
│
├── deploy/                      # Deployment configs
│   ├── docker-compose.yml       # 🆕 7-service stack
│   ├── Dockerfile               # Scraper container
│   └── Dockerfile.api           # API container
│
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

### 🆕 Analytics Data

With the new analytics system, data is also stored in:

- **PostgreSQL**: Normalized relational data for fast queries
- **MongoDB**: Raw JSON documents + LLM analysis results
- **Pre-calculated Metrics**: Judge/prosecutor/attorney performance scores
- **Recommendations**: Top attorney recommendations for common matchups

## Requirements

```bash
pip install -r requirements.txt
```

Requires Python 3.8+ and Playwright for browser automation.

## Documentation

### 🆕 Analytics Documentation

- **[Analytics Guide](docs/ANALYTICS_GUIDE.md)**: Complete user guide for the analytics system
- **[Implementation Summary](docs/IMPLEMENTATION_SUMMARY.md)**: Technical implementation details
- **[Architecture Plan](docs/ARCHITECTURE_ENHANCEMENT_PLAN.md)**: System architecture and design

### Original Documentation

- **Brad Davis Investigation**: See `docs/analysis/BRAD_DAVIS_EVIDENCE_SUMMARY.md`
- **October 2025 Analysis**: See `docs/reports/`
- **Deployment**: See `docs/README_deploy.md`
- **Watchdog**: See `docs/README_watchdog.md`

## 🚀 Quick Start (Analytics)

### 1. Setup

```bash
# Run automated setup
bash scripts/setup_analytics.sh

# Or manually:
pip install -r requirements.txt
cd deploy && docker-compose up -d
```

### 2. Import Existing Data

```bash
# Import 13,818+ existing cases into databases
python scripts/import_existing_data.py
```

### 3. Calculate Analytics

```bash
# Calculate performance metrics for all judges/prosecutors/attorneys
python scripts/calculate_analytics.py
```

### 4. Start API Server

```bash
# Start the REST API
cd deploy && docker-compose up -d api

# Access API docs at http://localhost:8000/docs
```

### 5. Get Attorney Recommendations

```bash
# Example: Get top 5 attorneys for a specific matchup
curl -X POST "http://localhost:8000/api/v1/recommendations" \
  -H "Content-Type: application/json" \
  -d '{
    "judge_id": 123,
    "prosecutor_id": 456,
    "charge_type": "VIOLENT",
    "top_n": 5
  }'
```

## 📊 Example Use Cases

### Use Case 1: Find Best Attorney

**Question**: "I'm charged with assault. Judge Smith (ID: 123) and Prosecutor Jones (ID: 456) are assigned. Which attorney should I hire?"

**API Call**:

```bash
curl -X POST "http://localhost:8000/api/v1/recommendations" \
  -d '{"judge_id": 123, "prosecutor_id": 456, "charge_type": "VIOLENT", "top_n": 5}'
```

**Result**: Top 5 attorneys ranked by predicted success rate for this specific matchup.

### Use Case 2: Analyze Matchup Difficulty

**Question**: "How difficult is this judge-prosecutor combination?"

**API Call**:

```bash
curl "http://localhost:8000/api/v1/matchup?judge_id=123&prosecutor_id=456"
```

**Result**: Difficulty level (VERY_DIFFICULT to VERY_FAVORABLE) with strategy suggestions.

### Use Case 3: Compare Attorneys

**Question**: "I'm considering 3 attorneys. Which one is best for my case?"

**API Call**:

```bash
curl -X POST "http://localhost:8000/api/v1/attorneys/compare" \
  -d '{"attorney_ids": [789, 790, 791], "judge_id": 123, "prosecutor_id": 456}'
```

**Result**: Side-by-side comparison with scores and metrics.

## Notes

- The scraper includes extensive retry logic and backoff strategies
- Large dockets (90+ entries) have extended wait times for complete loading
- PDF metadata is automatically extracted when available
- Currently tracking 13,818 cases across 2023-2025
