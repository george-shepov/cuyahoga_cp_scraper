# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automated web scraper for Cuyahoga County Common Pleas Court public records with **AI-powered attorney recommendation engine**. The system scrapes 13,818+ criminal cases (2023-2025), extracts structured data, stores it in dual databases (PostgreSQL + MongoDB), and provides ML-based analytics to answer: **"Which attorney should I hire given my judge and prosecutor?"**

**Tech Stack:**
- **Scraping**: Playwright (async browser automation), Pydantic validation, Rich UI
- **Databases**: PostgreSQL (analytics) + MongoDB (raw data)
- **LLM**: Ollama (local), OpenAI, Anthropic, Groq via LiteLLM
- **API**: FastAPI with Swagger docs at `/docs`
- **Deployment**: Docker Compose (7 services)
- **Background Tasks**: Celery + Redis

## Core Commands

### Scraping Operations

```bash
# Basic scraping with auto-detected year
python3 main.py scrape --start 678533 --limit 1

# Scrape with specific year
python3 main.py scrape --year 2023 --start 684826 --limit 10

# Scrape with PDF downloads (sentencing entries)
python3 main.py scrape --year 2023 --start 684826 --limit 5 --download-pdfs

# Get case statistics for a year
python3 main.py stats --year 2023

# Continuous scraper (never stops, checks hourly for new cases)
python3 continuous_scraper.py

# Repair incomplete/broken cases (multi-threaded, one thread per year)
python3 repair_incomplete_cases.py

# Download only sentencing entries (JE files) from all cases
python3 download_sentencing_only.py
```

### Analytics System

```bash
# Automated setup (installs deps, starts Docker, pulls Ollama model)
bash scripts/setup_analytics.sh

# Import 13,818+ existing cases into PostgreSQL + MongoDB
python3 scripts/import_existing_data.py

# Calculate performance metrics (judge/prosecutor/attorney analytics)
python3 scripts/calculate_analytics.py

# Start analytics API server
cd deploy && docker-compose up -d api
# Access Swagger docs: http://localhost:8000/docs

# Start all services (postgres, mongodb, redis, ollama, scraper, api, worker)
cd deploy && docker-compose up -d

# View logs for specific service
cd deploy && docker-compose logs -f api
cd deploy && docker-compose logs -f scraper
```

### Utilities

```bash
# Compare different versions of same case
python3 compare_versions.py CR-23-684826-A

# Analyze PDFs for a case
python3 analyze_pdfs.py CR-23-684826-A

# Scan for Brad B Davis metadata pattern (forensic investigation)
python3 scan_brad_davis.py

# Run statistics analysis and generate reports
python3 analyze_cases.py
```

### Docker Management

```bash
# Stop all services
cd deploy && docker-compose down

# Stop and remove volumes (clean slate)
cd deploy && docker-compose down -v

# Rebuild containers after code changes
cd deploy && docker-compose build

# View all running services
cd deploy && docker-compose ps
```

## Architecture

### Data Flow

```
Playwright Scraper → JSON (out/{year}/{case_id}.json)
                   ↓
            Import Script
                   ↓
        ┌──────────┴──────────┐
        ↓                     ↓
   PostgreSQL            MongoDB
(normalized tables)   (raw documents)
        ↓                     ↓
   Analytics              LLM Analysis
   Calculator            (Ollama/OpenAI)
        ↓                     ↓
        └──────────┬──────────┘
                   ↓
              FastAPI Server
                   ↓
         Attorney Recommendations
```

### Directory Structure

- **`main.py`** - Main Playwright scraper with retry logic, browser automation, JSON export
- **`continuous_scraper.py`** - Continuous scraper (runs indefinitely, checks hourly)
- **`repair_incomplete_cases.py`** - Multi-threaded repair system for broken JSONs
- **`out/{year}/`** - Scraped JSON files (`YYYY-NNNNNN_timestamp.json` format)
- **`api/main.py`** - FastAPI REST API with attorney recommendations
- **`database/`** - SQLAlchemy models (PostgreSQL) + Motor models (MongoDB)
  - `models_postgres.py` - Normalized relational schema (14 tables)
  - `models_mongo.py` - Document schemas
  - `analytics_models.py` - Performance metrics tables
- **`services/`** - Business logic layer
  - `attorney_recommender.py` - ML-based attorney ranking engine
  - `analytics_calculator.py` - Judge/prosecutor/attorney performance metrics
  - `quadrant_analyzer.py` - Multi-dimensional case categorization
  - `llm_service.py` - LiteLLM integration (Ollama, OpenAI, Anthropic, Groq)
  - `document_analyzer.py` - AI-powered PDF analysis
- **`scripts/`** - Utilities and setup automation
- **`deploy/`** - Docker Compose stack (postgres, mongodb, redis, ollama, scraper, api, worker)
- **`docs/`** - Documentation (`ANALYTICS_GUIDE.md`, `IMPLEMENTATION_SUMMARY.md`, etc.)
- **`_ARCHIVE/`** - Old scripts (73 files) - do not use

### Database Schema

**PostgreSQL Tables:**
- `cases` - Core case data (case_number, year, status, judge_id, timestamps)
- `defendants` - Defendant information (name, DOB, race, sex)
- `judges` - Judge master table (name, division)
- `prosecutors` - Prosecutor master table
- `attorneys` - Defense attorney master table (name, firm, role)
- `charges` - Criminal charges (statute, description, disposition)
- `docket_entries` - Chronological case events
- `costs` - Fines, fees, restitution
- `bonds` - Bond information
- `case_attorneys` - Many-to-many relationship
- `case_outcomes` - Final disposition data
- `case_metrics` - Calculated metrics (days_to_disposition, etc.)
- `judge_statistics` - Pre-calculated judge performance
- `prosecutor_statistics` - Pre-calculated prosecutor performance
- `defense_attorney_performance` - Pre-calculated attorney performance

**MongoDB Collections:**
- `raw_cases` - Full original scraped JSON
- `pdf_documents` - PDF binary storage + metadata
- `scrape_logs` - Audit trail
- `llm_analysis` - AI-generated insights

### JSON Output Schema

Each case JSON contains:
```json
{
  "summary": {
    "case_number": "CR-25-706402-A",
    "year": 2025,
    "number": 706402,
    "category": "CRIMINAL"
  },
  "defendant": {
    "name": "DOE, JOHN",
    "dob": "1990-01-01",
    "race": "BLACK",
    "sex": "MALE"
  },
  "docket": [
    {
      "seq": 1,
      "date": "2025-11-20",
      "description": "COMPLAINT FILED",
      "pdf_links": [...]
    }
  ],
  "costs": {
    "total": 500.00,
    "items": [...]
  },
  "attorneys": [
    {
      "name": "SMITH, JANE",
      "party": "DEFENDANT",
      "role": "DEFENSE"
    }
  ],
  "outcome": {
    "status": "PENDING",
    "disposition_date": null
  }
}
```

## Scraper Implementation Details

### Year Auto-Detection

The scraper automatically detects the year from case numbers:
1. Try scraping with case number as-is
2. If "No case was found", iterate through years 2020-2025
3. Cache the detected year for that case number range
4. See `docs/YEAR_AUTO_DETECTION.md` for details

### Retry Logic and Anti-Rate-Limiting

**Key locations in `main.py`:**
- `DEFAULT_DELAY = 300-800ms` - Polite delays between requests
- `@retry(stop_after_attempt(3), wait_fixed(2))` - Tenacity decorators
- Large dockets (90+ entries): Extended wait times for complete loading
- Stagnation detection: `STAGNATION_TIMEOUT=300s`, `STAGNATION_MAX_NO_SAVE=50`

### Browser Context Management

- **Headless mode**: `Cfg.headless = False` to see browser (default: headless)
- **Page lifecycle**: Each case gets fresh page via `browser.new_page()`
- **Cleanup**: Browsers killed aggressively in `repair_incomplete_cases.py` via `pkill -9 chromium`

### PDF Downloads

When `--download-pdfs` is used:
- PDFs saved to `out/{year}/{case_id}/` directory
- Only downloads sentencing entries (JE files) by default in `download_sentencing_only.py`
- PDF metadata extracted automatically (author, creation date, etc.)
- Brad Davis investigation: PDFs with "Brad B Davis" metadata pattern flagged

## Analytics System

### Attorney Recommendation Algorithm

**Location:** `services/attorney_recommender.py`

**Scoring factors:**
1. **Matchup Win Rate (40%)**: Historical performance with this judge-prosecutor combo
2. **Charge Type Win Rate (30%)**: Performance on this charge category (VIOLENT, DRUG, PROPERTY)
3. **Overall Win Rate (20%)**: General effectiveness
4. **Trial Performance (10%)**: Success rate when going to trial

**Minimum threshold:** 5 cases to be included in recommendations

### Quadrant Analysis System

**Location:** `services/quadrant_analyzer.py`

**Three quadrant types:**

1. **Severity vs. Complexity**
   - X-axis: Severity (0-10) based on charge types, violence
   - Y-axis: Complexity (0-10) based on # charges, co-defendants, docket entries

2. **Speed vs. Outcome**
   - X-axis: Speed (0-10) inverse of days to disposition
   - Y-axis: Outcome (0-10) favorability to defendant

3. **Cost vs. Representation**
   - X-axis: Cost (0-10) total fines/fees/restitution
   - Y-axis: Representation (0-10) attorney quality score

### LLM Integration

**Provider configuration** (via environment variables):
```bash
LLM_PROVIDER=ollama  # Options: ollama, openai, anthropic, groq
LLM_MODEL=llama3     # Model name
OPENAI_API_KEY=...   # Optional for OpenAI
ANTHROPIC_API_KEY=... # Optional for Claude
```

**Use cases:**
- Extract charges from unstructured text
- Sentiment analysis of docket entries
- PDF document classification
- Predictive case outcome modeling

## API Endpoints

**Base URL:** `http://localhost:8000`

**Key endpoints:**
- `POST /api/v1/recommendations` - Get top N attorney recommendations
- `GET /api/v1/matchup?judge_id=X&prosecutor_id=Y` - Analyze matchup difficulty
- `GET /api/v1/judges/{id}/performance` - Judge performance metrics
- `GET /api/v1/prosecutors/{id}/performance` - Prosecutor performance metrics
- `GET /api/v1/attorneys/{id}/performance` - Attorney performance metrics
- `POST /api/v1/attorneys/compare` - Side-by-side attorney comparison
- `GET /api/v1/cases/{id}/quadrant` - Quadrant analysis for case
- `POST /api/v1/documents/analyze` - AI-powered PDF analysis

**Interactive documentation:** `http://localhost:8000/docs`

## Environment Variables

```bash
# Scraper configuration
BASE_URL=https://cpdocket.cp.cuyahogacounty.gov
CASE_CATEGORY=CRIMINAL
YEAR=2025
START_NUMBER=706402
DIRECTION=both  # Options: up, down, both
LIMIT=100
DELAY_MS=300
DOWNLOAD_PDFS=false

# Database connections
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=cuyahoga_cases
POSTGRES_USER=cuyahoga
POSTGRES_PASSWORD=changeme

MONGO_HOST=mongodb
MONGO_PORT=27017
MONGO_DB=cuyahoga_cases
MONGO_USER=cuyahoga
MONGO_PASSWORD=changeme

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# LLM configuration
OLLAMA_BASE_URL=http://ollama:11434
LLM_PROVIDER=ollama
LLM_MODEL=llama3
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
```

## Common Workflows

### Scraping New Cases

```bash
# 1. Start with conservative settings
python3 main.py scrape --year 2025 --start 706500 --limit 10

# 2. Monitor output for errors
# 3. Adjust DELAY_MS if getting rate limited (increase delay)
# 4. Resume from last successful case if interrupted
```

### Setting Up Analytics from Scratch

```bash
# 1. Run automated setup
bash scripts/setup_analytics.sh

# 2. Import existing scraped data
python3 scripts/import_existing_data.py

# 3. Calculate analytics
python3 scripts/calculate_analytics.py

# 4. Start API server
cd deploy && docker-compose up -d api

# 5. Test recommendations
curl -X POST http://localhost:8000/api/v1/recommendations \
  -H "Content-Type: application/json" \
  -d '{"judge_id": 1, "prosecutor_id": 1, "charge_type": "VIOLENT", "top_n": 5}'
```

### Repairing Incomplete Data

```bash
# 1. Run repair system (scans all years, re-scrapes incomplete cases)
python3 repair_incomplete_cases.py

# 2. System will:
#    - Scan all JSONs for missing data (costs, attorneys, PDFs)
#    - Delete broken JSONs immediately
#    - Re-scrape with full data
#    - One thread per year for parallel processing
```

## Testing

**Browser visibility:** Set `headless: False` in `Cfg` class to watch scraper in action

**Single case test:**
```bash
python3 main.py scrape --year 2023 --start 684826 --limit 1
```

**Verify JSON output:**
```bash
jq . out/2023/2023-684826_*.json
```

## Important Notes

### Rate Limiting and Politeness

- Default delay: 300-800ms between requests
- Large dockets (90+ entries): Extended wait times
- If seeing "Access Denied" or timeouts: Increase `DELAY_MS` to 1000-2000ms
- Be respectful to court servers - this is public data but scraping should be reasonable

### Data Versioning

Cases are saved with timestamps: `{year}-{number}_YYYYMMDD_HHMMSS.json`
- Multiple versions of same case may exist (e.g., after updates)
- Use `compare_versions.py` to see differences
- Latest version by timestamp is canonical

### Case Repair System

The repair system in `repair_incomplete_cases.py` is aggressive:
- **Immediately deletes** broken JSONs (missing costs, attorneys, etc.)
- **Re-scrapes from scratch** with full data
- Uses `pkill -9` to kill zombie browser processes
- One thread per year for parallel processing
- Resume capability if interrupted

### Brad Davis Investigation

This codebase includes forensic investigation of Brad B Davis PDF metadata pattern:
- See `docs/analysis/BRAD_DAVIS_EVIDENCE_SUMMARY.md`
- `scan_brad_davis.py` scans for the pattern
- Not relevant to normal scraping operations

## Documentation

- **README.md** - High-level overview, quick start
- **docs/ANALYTICS_GUIDE.md** - Analytics system user guide
- **docs/IMPLEMENTATION_SUMMARY.md** - Technical implementation details
- **docs/ARCHITECTURE_ENHANCEMENT_PLAN.md** - System architecture and design
- **docs/YEAR_AUTO_DETECTION.md** - Year detection algorithm
- **docs/CASE_REPAIR_SYSTEM.md** - Repair system documentation

## Dependencies

Install via: `pip install -r requirements.txt`

**Key dependencies:**
- `playwright==1.47.0` - Browser automation
- `pydantic==2.9.2` - Data validation
- `rich==13.9.4` - Beautiful CLI output
- `tenacity==9.0.0` - Retry logic
- `sqlalchemy>=2.0.0` - PostgreSQL ORM
- `motor>=3.3.0` - MongoDB async driver
- `fastapi>=0.109.0` - REST API framework
- `litellm>=1.0.0` - Unified LLM interface
- `pandas==2.2.1`, `matplotlib==3.8.4`, `seaborn==0.13.2` - Data analysis

**Browser setup:**
```bash
playwright install chromium
```
