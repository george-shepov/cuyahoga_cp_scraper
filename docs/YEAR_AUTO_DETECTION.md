# Year Auto-Detection Feature

## Overview

The scraper can now automatically detect which year a case belongs to by searching the case number without specifying a year. This eliminates the need to manually specify `--year` when you only know the case number.

## How It Works

When you run the scraper without specifying `--year`, it:

1. Searches for the case number across all years
2. Extracts the year from the case ID format (e.g., `CR-23-678533-A` → 2023)
3. Uses the detected year for the scraping session

The case ID format uses 2-digit years:
- `CR-23-XXXXXX-A` → 2023
- `CR-24-XXXXXX-A` → 2024
- `CR-25-XXXXXX-A` → 2025

## Usage Examples

### Auto-detect year (recommended for unknown cases)
```bash
# Just provide the case number - year will be auto-detected
python3 main.py scrape --start 678533 --limit 1
# Output: ✓ Detected year: 2023 (from case ID pattern)

python3 main.py scrape --start 706402 --limit 1
# Output: ✓ Detected year: 2025 (from case ID pattern)
```

### Specify year manually (faster when you know it)
```bash
# Specify year directly to skip auto-detection
python3 main.py scrape --year 2023 --start 678533 --limit 1
```

## Benefits

1. **Convenience**: No need to remember which year a case is from
2. **Accuracy**: Eliminates year specification errors
3. **Flexibility**: Works with any case number across 2023-2025
4. **User-friendly**: Matches how you'd search on the court website

## Technical Details

The auto-detection:
- Opens a browser session
- Submits a search with only the case number (no year)
- Parses the result page for the full case ID
- Extracts the 2-digit year and converts to 4-digit format
- Closes the detection browser and proceeds with normal scraping

## Fallback Behavior

If auto-detection fails:
- Falls back to the `YEAR` environment variable
- If no env variable, defaults to 2025
- Shows a warning message indicating the fallback

## Example Output

```
──────────────────────────── 🔍 Auto-detecting year for case 678533 ────────────────────────────
🔍 Auto-detecting year for case 678533...
Navigating to Search.aspx...
Skipping year selection to search across all years
Filled case number: 678533
✓ Detected year: 2023 (from case ID pattern)
✓ Using auto-detected year: 2023
──────────────────── Cuyahoga CP Scraper  year=2023 start=678533 direction=both limit=1 ────────────────────
```

## When to Use Manual Year Specification

Use `--year` when:
- You know the year (saves ~5-10 seconds)
- Scraping large batches (small performance gain)
- Year auto-detection is failing consistently

## Notes

- Auto-detection adds ~5-10 seconds to startup time
- Only runs once at the start of scraping
- Not used when `--discover-years` flag is set
- Works for all criminal cases in the system
