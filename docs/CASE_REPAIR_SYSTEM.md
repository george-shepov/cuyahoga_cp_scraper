# Multi-Threaded Case Repair System

## Overview

The repair system automatically identifies and fixes incomplete or broken case JSONs by:
1. Scanning all existing JSONs for missing data
2. **Immediately deleting** broken JSONs
3. Re-scraping to get complete data
4. Running one thread per year for parallel processing

## What It Detects

The system identifies cases with:
- **No costs** - Missing cost information
- **No attorneys** - Missing attorney data
- **No docket** - Missing docket entries
- **No parties** - Missing party information
- **No case info** - Missing summary/metadata
- **No disposition** - Missing disposition information
- **Scrape errors** - Cases that had errors during initial scrape
- **Corrupted JSON** - Files that can't be parsed

## Usage

```bash
# Run repair system (scans and repairs all years)
python3 repair_incomplete_cases.py
```

The script will:
1. Start 3 worker threads (one per year: 2023, 2024, 2025)
2. Each worker scans its year for issues
3. Workers repair cases in parallel
4. Show real-time progress and results
5. Save detailed results to `repair_results_{timestamp}.json`

## How It Works

### Scanning Phase
Each worker:
- Loads all JSON files for its year
- Checks for missing/incomplete data fields
- Categorizes issues found

### Repair Phase
For each broken case:
1. **Extract case number** from case_id or filename
2. **Delete broken JSON immediately**
3. **Re-scrape** with `python3 main.py scrape --year X --start N --limit 1 --headless`
4. **Verify** new JSON exists and issues are fixed
5. **Report** success or failure

### Verification
After re-scraping, the system verifies:
- New JSON file was created
- JSON is valid (can be parsed)
- Previously missing data is now present
- No new errors were introduced

## Performance

- **Parallel processing**: 3 threads running simultaneously (one per year)
- **Immediate deletion**: Frees up space as soon as broken files are identified
- **Timeout protection**: 2 minute timeout per case prevents hangs
- **Progress tracking**: Real-time console output shows current status

## Output

### Console Output
```
═══════════════════════════════ 🔧 Multi-Threaded Case Repair System ════════════════════════════════
Output directory: out
Years to process: 2023, 2024, 2025
Workers: 3 (one per year)

──────────────────────────── Worker 1: Processing Year 2023 ────────────────────────────
Worker 1 (Year 2023): Scanning 10568 cases...
Worker 1: Found 10568 cases with issues in 2023
Worker 1: Issue breakdown:
  • no_disposition: 10568
  • no_attorneys: 7206
  • no_costs: 4434
  • no_docket: 4256

Worker 1: [1/10568] CR-23-677834-A (2023): no_costs, no_attorneys, no_disposition
Worker 1: Deleting broken JSON: 2023-677834_20251112_160720.json
Worker 1: Re-scraping CR-23-677834-A (case #677834)...
Worker 1: ✓ Repaired CR-23-677834-A → 2023-677834_20251116_124921.json
```

### Results File
Saves to `repair_results_{timestamp}.json`:
```json
{
  "timestamp": "2025-11-16T12:49:21",
  "duration_seconds": 1234.5,
  "total_scanned": 15047,
  "total_issues": 15047,
  "total_repaired": 14500,
  "total_failed": 547,
  "results": [
    {
      "year": 2023,
      "worker_id": 1,
      "scanned": 10568,
      "issues_found": 10568,
      "repaired": 10100,
      "failed": 468
    }
  ]
}
```

## Common Issues & Solutions

### Issue: "Cannot extract case number"
**Cause**: Case ID format doesn't match expected pattern  
**Solution**: Script now tries multiple extraction methods (case_id, filename)

### Issue: "Re-scrape didn't create JSON"
**Cause**: Scraper may have encountered error or case doesn't exist  
**Solution**: Logged as failed; manual investigation needed

### Issue: "Re-scraped but issues remain"
**Cause**: Missing data may not exist in source system  
**Solution**: Logged as warning; case may be incomplete in court system

## Best Practices

1. **Run during off-hours** - Less load on court website
2. **Monitor progress** - Check console output for errors
3. **Review results file** - Identify patterns in failures
4. **Re-run if needed** - Some failures may succeed on retry
5. **Backup before running** - Though old files are deleted, good practice

## Integration with Main Scraper

The repair system uses the same scraper (`main.py`) so:
- Same authentication/session handling
- Same retry logic and backoff
- Same data extraction methods
- Guaranteed consistency with original scrapes

## Limitations

- **2 minute timeout** per case (prevents indefinite hangs)
- **No PDF download** during repair (focused on JSON completeness)
- **Sequential within year** (one case at a time per worker)
- **Requires manual review** of failed cases

## Future Enhancements

Potential improvements:
- Selective repair (only fix specific issue types)
- PDF download during repair
- Configurable timeout per case
- Retry logic for failed repairs
- Email notifications when complete

## Example Run

```bash
$ python3 repair_incomplete_cases.py

════════════════════════════ 🔧 Multi-Threaded Case Repair System ═══════════════════════════
Output directory: out
Years to process: 2023, 2024, 2025
Workers: 3 (one per year)

Starting parallel repair workers...

[3 workers run in parallel, repairing 15,000+ cases...]

═══════════════════════════════════ 🎉 Repair Complete ══════════════════════════════════════

Total cases scanned: 15,047
Issues found: 15,047
Successfully repaired: 14,500
Failed repairs: 547
Duration: 1234.5 seconds

Per-Year Results:
  2023: 10100/10568 repaired
  2024: 195/203 repaired
  2025: 4205/4276 repaired

Results saved to: repair_results_20251116_124921.json
```

## Notes

- The repair system is **destructive** - it deletes broken files immediately
- Always creates fresh JSONs from live court data
- Parallel execution significantly speeds up large-scale repairs
- Safe to interrupt (Ctrl+C) - only affects in-progress case
