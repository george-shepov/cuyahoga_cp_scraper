#!/usr/bin/env python3
"""
ULTRA-RELIABLE SCRAPER - Ensures complete coverage
- Resumes from 680204
- Retries all failed cases up to 3 times
- Validates EVERY file exists before counting
- Detects and reports gaps
- Robust Chrome crash handling
- Reports missing/failed cases at end
"""
import subprocess
import json
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict

RESUME = Path("scrape_677500_707148_PARALLEL_resume.txt")
START = 677500
END = 707148
WORKERS = 8
REQUEST_DELAY = 0.3
MAX_RETRIES = 3  # Retry each failed case up to 3 times

def get_pos():
    if RESUME.exists():
        try:
            pos = int(RESUME.read_text().strip())
            if START <= pos <= END:
                return pos
        except:
            pass
    return START

def save_pos(n):
    RESUME.write_text(str(n))

def get_year(case):
    if case < 695000:
        return 2023
    elif case < 700000:
        return 2024
    else:
        return 2025

def file_exists_and_valid(case, yr):
    """Check if file actually exists on disk and is valid"""
    year_dir = Path(f"out/{yr}")
    if not year_dir.exists():
        return False
    
    matches = list(year_dir.glob(f"{yr}-{case:06d}_*.json"))
    if not matches:
        return False
    
    try:
        for f in matches:
            data = json.loads(f.read_text())
            if data.get('metadata', {}).get('exists'):
                return True
    except:
        pass
    
    return False

def scrape_case(case, yr, attempt=1):
    """Scrape single case with retry logic"""
    try:
        result = subprocess.run(
            ["python3", "main.py", "scrape", "--year", str(yr), 
             "--start", str(case), "--limit", "1", "--direction", "up"],
            capture_output=True, timeout=180, text=True
        )
        
        time.sleep(0.2)
        
        if file_exists_and_valid(case, yr):
            return True, None
        
        if "No cases found" in result.stdout.lower() or "No cases found" in result.stderr.lower():
            return False, "NOT_FOUND"
        
        error = result.stderr[:80] if result.stderr else result.stdout[:80]
        return False, error
        
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except Exception as e:
        return False, str(e)[:80]

def scrape_reliable():
    """Scrape with reliability - retry all failures"""
    
    start_pos = get_pos()
    
    print(f"\n{'='*80}")
    print(f"ULTRA-RELIABLE SCRAPER - COMPLETE COVERAGE")
    print(f"{'='*80}")
    print(f"Resume Position: {start_pos}")
    print(f"Range: {START} → {END} ({END-START+1:,} cases total)")
    print(f"Workers: {WORKERS}")
    print(f"Max Retries: {MAX_RETRIES} per case")
    print(f"✓ Will retry ALL failures")
    print(f"✓ Will validate ALL files exist")
    print(f"✓ Will detect gaps")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    found = set()
    failed = {}  # case -> error
    missing = set()
    
    cur = start_pos
    total_processed = 0
    batch_num = 0
    
    # First pass: get all we can
    while cur <= END:
        batch_num += 1
        batch_start = cur
        batch_cases = []
        
        # Create batch
        for i in range(WORKERS):
            if cur > END:
                break
            batch_cases.append(cur)
            cur += 1
        
        print(f"\n[Pass 1, Batch {batch_num:4d}] Cases {batch_start:7d}-{cur-1:7d}")
        print(f"  Processing: ", end="", flush=True)
        
        for case in batch_cases:
            yr = get_year(case)
            success, error = scrape_case(case, yr)
            
            if success:
                found.add(case)
                total_processed += 1
                print(f"✓", end="", flush=True)
                save_pos(case + 1)
            else:
                if error == "NOT_FOUND":
                    missing.add(case)
                    print(f"⊝", end="", flush=True)
                else:
                    failed[case] = error
                    print(f"✗", end="", flush=True)
                save_pos(case + 1)
            
            time.sleep(REQUEST_DELAY)
        
        print()
        print(f"  Found: {len(found):,} | Failed: {len(failed)} | Missing: {len(missing)}")
        pct = 100 * (cur - START) / (END - START + 1)
        print(f"  Progress: {cur:,} / {END:,} ({pct:.1f}%)")
    
    # Second pass: retry all failures
    if failed:
        print(f"\n{'='*80}")
        print(f"RETRY PASS - {len(failed)} failed cases")
        print(f"{'='*80}")
        
        retry_batch = 0
        for attempt in range(2, MAX_RETRIES + 1):
            print(f"\n[Attempt {attempt}/{MAX_RETRIES}] Retrying {len(failed)} cases...")
            print(f"  Processing: ", end="", flush=True)
            
            still_failed = {}
            
            for case in sorted(failed.keys()):
                yr = get_year(case)
                success, error = scrape_case(case, yr, attempt)
                
                if success:
                    found.add(case)
                    if case in failed:
                        del failed[case]
                    print(f"✓", end="", flush=True)
                else:
                    still_failed[case] = error
                    print(f"✗", end="", flush=True)
                
                time.sleep(REQUEST_DELAY)
            
            failed = still_failed
            print()
            print(f"  Recovered: {len(found) - len(missing) - len(failed)} | Still failing: {len(failed)}")
            
            if not failed:
                break
    
    # Third pass: validate all found files actually exist
    print(f"\n{'='*80}")
    print(f"VALIDATION PASS - Checking all {len(found)} files exist")
    print(f"{'='*80}\n")
    
    validated = set()
    for case in sorted(found):
        yr = get_year(case)
        if file_exists_and_valid(case, yr):
            validated.add(case)
        else:
            print(f"⚠️  File missing on disk: {yr}-{case:06d}")
            failed[case] = "FILE_MISSING_AFTER_SAVE"
    
    # Detect gaps
    print(f"\n{'='*80}")
    print(f"GAP DETECTION")
    print(f"{'='*80}\n")
    
    gaps = []
    in_gap = False
    gap_start = None
    
    for case in range(START, END + 1):
        if case not in validated and case not in missing:
            if not in_gap:
                gap_start = case
                in_gap = True
        else:
            if in_gap:
                gaps.append((gap_start, case - 1))
                in_gap = False
    
    if in_gap:
        gaps.append((gap_start, END))
    
    if gaps:
        print(f"Found {len(gaps)} gap(s):")
        for start, end in gaps:
            gap_size = end - start + 1
            print(f"  {start:7d} - {end:7d} ({gap_size:,} cases)")
    else:
        print(f"✓ No gaps detected!")
    
    # Final report
    print(f"\n{'='*80}")
    print(f"FINAL REPORT")
    print(f"{'='*80}\n")
    
    total_range = END - START + 1
    print(f"Total Range: {total_range:,}")
    print(f"✅ Successfully Saved: {len(validated):,}")
    print(f"⊝ Not Found (Missing): {len(missing):,}")
    print(f"✗ Failed/Error: {len(failed):,}")
    
    if failed:
        print(f"\n⚠️  FAILED CASES ({len(failed)}):")
        for case in sorted(failed.keys())[:20]:  # Show first 20
            print(f"  {get_year(case)}-{case:06d}: {failed[case]}")
        if len(failed) > 20:
            print(f"  ... and {len(failed) - 20} more")
    
    # File counts
    counts = {"2023": 0, "2024": 0, "2025": 0}
    for yr in [2023, 2024, 2025]:
        yr_dir = Path(f"out/{yr}")
        if yr_dir.exists():
            counts[str(yr)] = len(list(yr_dir.glob("*.json")))
    
    print(f"\n📁 FILES ON DISK:")
    print(f"  2023: {counts['2023']} files")
    print(f"  2024: {counts['2024']} files")
    print(f"  2025: {counts['2025']} files")
    print(f"  Total: {sum(counts.values())} files")
    
    completion_pct = 100 * len(validated) / total_range
    print(f"\n📊 COMPLETION: {completion_pct:.1f}%")
    
    print(f"\n⏱️  Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

if __name__ == "__main__":
    scrape_reliable()
