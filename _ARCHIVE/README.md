# Cuyahoga County Common Pleas Court Scraper

A web scraper for extracting case information from the Cuyahoga County Common Pleas Court online docket system using Playwright for browser automation.

## Features

- **Robust TOS Handling**: Automatically detects and accepts Terms of Service pages
- **Persistent Browser Context**: Uses authenticated browser sessions to avoid repeated redirects
- **Comprehensive Page Checking**: Monitors page state to handle unexpected redirects
- **Multiple Submission Strategies**: Tries various methods to submit search forms
- **Detailed Logging**: Rich console output with debugging information
- **Resume Capability**: Can resume scraping from the last processed case
- **Data Extraction**: Extracts Summary, Docket, Costs, Defendant, and Attorney information
- **Error Recovery**: Retry mechanisms with exponential backoff

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd cuyahoga_cp_scraper
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Install Playwright browsers:

```bash
playwright install chromium
```

## Usage

### Basic Usage

```bash
python main.py --year 2025 --start 706402 --limit 10
```

### Command Line Options

- `--year`: Case year (default: 2025)
- `--start`: Starting case number (default: 706402)  
- `--limit`: Number of cases to process (default: 100)
- `--direction`: Search direction - `up`, `down`, or `both` (default: both)
- `--output-dir`: Output directory (default: ./out)
- `--delay-ms`: Delay between requests in milliseconds (default: 1250)
- `--headless`: Run in headless mode
- `--resume`: Resume from last processed case

### Environment Variables

You can also configure the scraper using environment variables:

```bash
export YEAR=2025
export START_NUMBER=706402
export LIMIT=50
export DIRECTION=both
export OUTPUT_DIR=./out
export DELAY_MS=1000
export HEADLESS=false
```

### Examples

Search specific range:
```bash
python main.py --year 2025 --start 706400 --limit 20 --direction up
```

Resume interrupted scraping:
```bash
python main.py --resume
```

Run in headless mode with faster processing:
```bash
python main.py --headless --delay-ms 500
```

## Output Structure

```
out/
├── 2025/
│   ├── 706402/
│   │   ├── case.json          # Combined case data
│   │   ├── summary.html       # Case summary page
│   │   ├── docket.html        # Docket entries
│   │   ├── costs.html         # Court costs
│   │   ├── defendant.html     # Defendant information
│   │   └── attorney.html      # Attorney information
│   ├── .last_number          # Resume state
│   └── trace.zip             # Playwright trace for debugging
```

## Technical Details

### Architecture

- **Playwright**: Browser automation with Chromium
- **Rich**: Enhanced console output and progress tracking
- **Tenacity**: Retry mechanisms for reliability
- **Pydantic**: Configuration validation
- **Persistent Context**: Maintains authenticated browser sessions

### Key Functions

- `navigate_to_search()`: Handles TOS and navigates to search form
- `search_case()`: Submits search and extracts case ID
- `snapshot_case()`: Extracts all case information
- `ensure_past_tos()`: Comprehensive TOS page handling
- `check_current_page()`: Page state monitoring

### Error Handling

The scraper includes comprehensive error handling:
- TOS redirect detection and handling
- Form submission failures with multiple fallback strategies
- Network timeouts with retry mechanisms
- Debug HTML output for troubleshooting

## Debugging

Debug files are automatically created in the `out/` directory:
- `debug_before_submit.html`: Form state before submission
- `debug_after_submit.html`: Response after submission
- `debug_tos.html`: TOS page content
- `debug_stuck_on_search.html`: Search page when stuck
- `trace.zip`: Playwright execution trace

## Legal Notice

This tool is for educational and research purposes only. Users are responsible for compliance with the website's terms of service and applicable laws. The scraper includes polite delays and respects the site's structure.

## License

MIT License - see LICENSE file for details.

1. Accept terms (if shown)
2. Navigate to **Criminal Search by Case**
3. Select **Year**, enter the **6-digit case number**
4. Load the case and visit tabs: **Summary, Docket, Costs, Defendant, Attorney**
5. Save: raw HTML snapshots and a merged `case.json` per case
6. Move to the **next** and **previous** sequential case numbers as requested
7. Gracefully handle "No cases found" error pages

> The script throttles requests and logs each step. It **does not** blast the site.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install
cp .env.example .env   # then adjust as needed
python main.py --year 2025 --start 706402 --limit 50 --direction both
```
