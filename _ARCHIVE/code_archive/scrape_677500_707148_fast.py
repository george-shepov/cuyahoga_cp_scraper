#!/usr/bin/env python3
"""
Fast parallel scraper using simple_continuous pattern
677500 -> 707148 with 50 workers (reduced to avoid bans)
"""
import subprocess
import sys
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from collections import defaultdict

RESUME = Path("scrape_677500_707148_resume.txt")
START = 677500
END = 707148
WORKERS = 50

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
    """Get year from case number"""
    if case < 695000:
        return 2023
    elif case < 700000:
        return 2024
    else:
        return 2025

def get_year_from_file(case, yr):
    """Verify year from actual file"""
    try:
        matches = list(Path(f"out/{yr}").glob(f"{yr}-{case}_*.json"))
        if not matches:
            return yr
        with open(matches[0]) as f:
            data = json.load(f)
            if not data.get('metadata', {}).get('exists'):
                return None
            return yr
    except:
        return yr

def scrape(case):
    """Scrape single case"""
    yr = get_year(case)
    try:
        r = subprocess.run(
            ["python3", "main.py", "scrape", "--year", str(yr), 
             "--start", str(case), "--limit", "1", "--direction", "up"],
            capture_output=True, timeout=90, text=True
        )
        
        if r.returncode == 0:
            actual_yr = get_year_from_file(case, yr)
            if actual_yr:
                return (case, True, yr, False)
        
        # Check if "not found"
        if "not found" in r.stdout.lower() or "404" in r.stdout.lower():
            return (case, False, yr, True)  # is_empty = True
        
        return (case, False, yr, False)
    except:
        return (case, False, yr, False)

def main():
    start_pos = get_pos()
    
    print(f"\n{'='*80}")
    print(f"PARALLEL SCRAPER: {START} → {END}")
    print(f"{'='*80}")
    print(f"Start Position: {start_pos}")
    print(f"Workers: {WORKERS}")
    print(f"Total to scrape: {END - start_pos + 1:,}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    found_count = 0
    missing_count = 0
    error_count = 0
    consecutive_empty = 0
    MAX_CONSECUTIVE_EMPTY = 20
    
    gap_log = []
    current_gap_start = None
    
    cur = start_pos
    batch_num = 0
    total_processed = 0
    
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        while cur <= END:
            batch_num += 1
            batch_start = cur
            batch_cases = []
            futures = {}
            
            # Submit batch
            for i in range(WORKERS):
                if cur > END:
                    break
                f = ex.submit(scrape, cur)
                futures[f] = cur
                batch_cases.append(cur)
                cur += 1
            
            print(f"[Batch {batch_num:4d}] Cases {batch_start:7d}-{cur-1:7d} ({len(batch_cases)} submitted)...", end=" ", flush=True)
            
            # Process results
            batch_found = 0
            batch_empty = 0
            batch_errors = 0
            
            for f in as_completed(futures):
                case, found, yr, is_empty = f.result()
                total_processed += 1
                
                if found:
                    found_count += 1
                    batch_found += 1
                    consecutive_empty = 0
                    
                    # End gap if we were in one
                    if current_gap_start is not None:
                        gap_size = case - current_gap_start
                        gap_log.append((current_gap_start, case - 1, gap_size))
                        current_gap_start = None
                    
                    save_pos(case + 1)
                
                elif is_empty:
                    missing_count += 1
                    batch_empty += 1
                    consecutive_empty += 1
                    
                    # Track gap start
                    if current_gap_start is None:
                        current_gap_start = case
                    
                    # Stop if too many consecutive empties
                    if consecutive_empty >= MAX_CONSECUTIVE_EMPTY:
                        print(f"\n⚠️  STOPPING: {consecutive_empty} consecutive empty results")
                        return finalize(found_count, missing_count, error_count, gap_log)
                    
                    save_pos(case + 1)
                
                else:
                    error_count += 1
                    batch_errors += 1
                    consecutive_empty = 0
            
            print(f"✓ {batch_found} found, {batch_empty} empty, {batch_errors} errors")
            
            if batch_num % 5 == 0:
                print(f"  📊 Total: {found_count:,} found, {missing_count:,} missing, {error_count} errors")
                print(f"  Position: {cur:,} / {END:,} ({100*(cur-START)/(END-START+1):.1f}%)\n")
    
    return finalize(found_count, missing_count, error_count, gap_log)

def finalize(found, missing, errors, gaps):
    """Print final report"""
    total = found + missing
    
    print(f"\n{'='*80}")
    print(f"SCRAPE COMPLETE")
    print(f"{'='*80}\n")
    
    print(f"✅ Found: {found:,}")
    print(f"❌ Missing: {missing:,}")
    print(f"⚠️  Errors: {errors}")
    print(f"📊 Coverage: {100*found/(found+missing):.1f}%")
    print(f"\n🔍 Gaps: {len(gaps)}")
    
    if gaps:
        print("\nFirst 20 gaps:")
        for start, end, size in gaps[:20]:
            print(f"   {start:7d} - {end:7d}: {size:6,d} cases")
        if len(gaps) > 20:
            print(f"   ... and {len(gaps)-20} more")
    
    # Save log
    with open("SCRAPE_677500_707148_LOG.txt", "w") as f:
        f.write(f"PARALLEL SCRAPE RESULTS\n")
        f.write(f"Range: {START} → {END}\n")
        f.write(f"Workers: {WORKERS}\n")
        f.write(f"{'='*80}\n\n")
        f.write(f"Found: {found}\n")
        f.write(f"Missing: {missing}\n")
        f.write(f"Errors: {errors}\n\n")
        f.write(f"GAPS:\n")
        for start, end, size in gaps:
            f.write(f"{start} - {end}: {size}\n")
    
    print(f"\n📋 Log: SCRAPE_677500_707148_LOG.txt")
    print(f"⏱️  Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

if __name__ == "__main__":
    main()
