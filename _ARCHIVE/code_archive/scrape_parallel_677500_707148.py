#!/usr/bin/env python3
"""
Parallel range scraper: 677500 -> 707148
Uses ThreadPoolExecutor with 20 workers for speed
Validates writes before continuing
Logs all gaps and errors
"""

import subprocess
import json
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import time

START_CASE = 677500
END_CASE = 707148
OUT_DIR = Path("out")
WORKERS = 20
BATCH_SIZE = 100

def get_year_from_case(case_num):
    """Determine year based on case number"""
    if case_num < 695000:
        return 2023
    elif case_num < 700000:
        return 2024
    else:
        return 2025

def scrape(case):
    """Scrape a single case using main.py"""
    yr = get_year_from_case(case)
    try:
        r = subprocess.run(
            ["python3", "main.py", "scrape", "--year", str(yr),
             "--start", str(case), "--limit", "1", "--direction", "up"],
            capture_output=True, timeout=60, text=True
        )
        
        if r.returncode != 0:
            return (case, False, "error")
        
        if "not found" in r.stdout.lower() or "404" in r.stdout.lower():
            return (case, False, "not_found")
        
        # Check if file was created
        year_dir = OUT_DIR / str(yr)
        if year_dir.exists():
            files = list(year_dir.glob(f"*{case:06d}*.json"))
            if files:
                return (case, True, "found")
        
        return (case, False, "no_file")
    except subprocess.TimeoutExpired:
        return (case, False, "timeout")
    except Exception as e:
        return (case, False, "exception")

def main():
    print(f"\n{'='*80}")
    print(f"PARALLEL RANGE SCRAPE: {START_CASE} → {END_CASE}")
    print(f"{'='*80}\n")
    
    total_to_scrape = END_CASE - START_CASE + 1
    num_batches = (total_to_scrape + BATCH_SIZE - 1) // BATCH_SIZE
    
    print(f"📊 Total cases: {total_to_scrape:,}")
    print(f"🔀 Workers: {WORKERS}")
    print(f"📦 Batch size: {BATCH_SIZE}")
    print(f"📦 Total batches: {num_batches}")
    print(f"⏱️  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    all_found = set()
    all_missing = set()
    errors = defaultdict(int)
    gap_log = []
    
    for batch_idx in range(num_batches):
        batch_start = START_CASE + (batch_idx * BATCH_SIZE)
        batch_end = min(batch_start + BATCH_SIZE - 1, END_CASE)
        
        cases_to_scrape = list(range(batch_start, batch_end + 1))
        
        print(f"[Batch {batch_idx+1:4d}/{num_batches:4d}] Scraping {batch_start:7d} - {batch_end:7d}...")
        
        # Parallel scrape this batch
        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            futures = {executor.submit(scrape, case): case for case in cases_to_scrape}
            
            completed = 0
            for future in as_completed(futures):
                case, found, status = future.result()
                completed += 1
                
                if found:
                    all_found.add(case)
                else:
                    all_missing.add(case)
                    errors[status] += 1
        
        # After batch, check what we have
        found_in_batch = len([c for c in cases_to_scrape if c in all_found])
        missing_in_batch = BATCH_SIZE - found_in_batch
        
        print(f"  ✓ {found_in_batch}/{BATCH_SIZE} cases found")
        
        # Detect gaps in this batch
        current_gap_start = None
        for case in cases_to_scrape:
            if case not in all_found:
                if current_gap_start is None:
                    current_gap_start = case
            else:
                if current_gap_start is not None:
                    gap_size = case - current_gap_start
                    gap_log.append((current_gap_start, case - 1, gap_size))
                    current_gap_start = None
        
        if current_gap_start is not None and batch_idx == num_batches - 1:
            gap_size = batch_end - current_gap_start + 1
            gap_log.append((current_gap_start, batch_end, gap_size))
        
        print(f"  📊 Progress: {len(all_found):,} found, {len(all_missing):,} missing\n")
    
    # Final report
    print(f"\n{'='*80}")
    print(f"SCRAPE COMPLETE")
    print(f"{'='*80}\n")
    
    total_found = len(all_found)
    total_missing = len(all_missing)
    
    print(f"✅ FOUND: {total_found:,} cases")
    print(f"❌ MISSING: {total_missing:,} cases")
    print(f"📊 Coverage: {100*total_found/total_to_scrape:.1f}%")
    
    print(f"\n📋 ERRORS BY TYPE:")
    for error_type, count in sorted(errors.items(), key=lambda x: -x[1]):
        print(f"   {error_type}: {count:,}")
    
    if gap_log:
        print(f"\n🔍 GAPS DETECTED ({len(gap_log)} gaps, showing first 30):")
        for gap_start, gap_end, gap_size in gap_log[:30]:
            print(f"   {gap_start:7d} - {gap_end:7d}: {gap_size:6,d} cases")
        if len(gap_log) > 30:
            print(f"   ... and {len(gap_log)-30} more gaps")
    
    print(f"\n⏱️  Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Save log
    log_file = Path("SCRAPE_677500_707148_LOG.txt")
    with open(log_file, 'w') as f:
        f.write(f"PARALLEL SCRAPE RESULTS\n")
        f.write(f"Range: {START_CASE} → {END_CASE}\n")
        f.write(f"Workers: {WORKERS}\n")
        f.write(f"{'='*80}\n\n")
        
        f.write(f"SUMMARY:\n")
        f.write(f"Found: {total_found:,} cases\n")
        f.write(f"Missing: {total_missing:,} cases\n")
        f.write(f"Coverage: {100*total_found/total_to_scrape:.1f}%\n\n")
        
        f.write(f"ERRORS:\n")
        for error_type, count in sorted(errors.items(), key=lambda x: -x[1]):
            f.write(f"{error_type}: {count}\n")
        
        f.write(f"\nGAPS ({len(gap_log)} total):\n")
        for gap_start, gap_end, gap_size in gap_log:
            f.write(f"{gap_start:7d} - {gap_end:7d}: {gap_size:6,d} cases\n")
        
        f.write(f"\nFOUND CASES (sample of first 100):\n")
        for case_num in sorted(all_found)[:100]:
            f.write(f"{case_num}\n")
    
    print(f"📋 Log saved: {log_file}\n")

if __name__ == "__main__":
    main()
