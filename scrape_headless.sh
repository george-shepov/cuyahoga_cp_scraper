#!/bin/bash
# Headless scraper wrapper - ensures browsers stay hidden and get killed

export HEADLESS=true
YEAR=$1
CASE=$2

# Run scraper in headless mode
python3 main.py scrape --year "$YEAR" --start "$CASE" --limit 1 --headless 2>&1

# Immediately kill any browsers
pkill -9 -f "chromium" 2>/dev/null
pkill -9 -f "playwright" 2>/dev/null

exit 0
