#!/bin/bash
# Gap-fill scraper: fills missing case numbers across 2023-2026
# - Downloads only indictment (CR) PDF per case
# - Skips cases already scraped
# - Runs years sequentially

set -e
cd "$(dirname "$0")"
source .venv/bin/activate

echo "=== Gap-fill: 2023 (677500-687965, ~1473 missing) ==="
python3 main.py scrape --year 2023 --start 677500 --limit 10466 --direction up \
  --skip-existing --headless --delay-ms 400 --pdf-types CR

echo "=== Gap-fill: 2024 (687966-698224, ~3967 missing) ==="
python3 main.py scrape --year 2024 --start 687966 --limit 10259 --direction up \
  --skip-existing --headless --delay-ms 400 --pdf-types CR

echo "=== Gap-fill: 2025 (698242-708459, ~1763 missing) ==="
python3 main.py scrape --year 2025 --start 698242 --limit 10218 --direction up \
  --skip-existing --headless --delay-ms 400 --pdf-types CR

echo "=== Gap-fill: 2026 (709000-711854, ~360 missing) ==="
python3 main.py scrape --year 2026 --start 709000 --limit 2855 --direction up \
  --skip-existing --headless --delay-ms 400 --pdf-types CR

echo "=== Done with gap-fill. All years complete. ==="
