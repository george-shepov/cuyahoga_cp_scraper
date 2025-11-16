#!/usr/bin/env python3
"""
FIXED parallel scraper - verifies files are actually written to disk
677500 -> 707148 with 25 workers (reduced for stability)
"""
import subprocess
import sys
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from collections import defaultdict

RESUME = Path("scrape_677500_707148_resume.txt")
START = 677500
END = 707148
WORKERS = 25  # Reduced from 50 for stability

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

def file_exists_and_valid(case, yr):
    """Check if file actually exists on disk and is valid"""
    year_dir = Path(f"out/{yr}")
    if not year_dir.exists():
        return False
    
    # Look for files matching this case
    matches = list(year_dir.glob(f"{yr}-{case:06d}_*.json"))
    if not matches:
        return False
    
    # Verify the file is valid JSON and has content
    try:
        for f in matches:
            data = json.loads(f.read_text())
            if data.get('metadata', {}).get('exists'):
                return True
    except:
        pass
    
    return False

def scrape(case):
    """Scrape single case - returns (case, found, yr, is_empty)"""
    yr = get_year(case)
    try:
        # Run main.py
        r = subprocess.run(
            ["python3", "main.py", "scrape", "--year", str(yr), 
             "--start", str(case), "--limit", "1", "--direction", "up"],
            capture_output=True, timeout=120, text=True
        )
        
        # IMPORTANT: Verify file actually exists, don't just trust return code
        time.sleep(0.1)  # Small delay to ensure write completes
        
        if file_exists_and_valid(case, yr):
            return (case, True, yr, False)  # found=True, is_empty=False
        
        # Check if "not found"
        if "not found" in r.stdout.lower() or "404" in r.stdout.lower() or "not found" in r.stderr.lower():
            return (case, False, yr, True)  # found=False, is_empty=True
        
        return (case, False, yr, False)  # found=False, is_empty=False (error)
    except subprocess.TimeoutExpired:
        return (case, False, yr, False)  # Timeout = error
    except Exception as e:
        return (case, False, yr, False)  # Exception = error

def main():
    start_pos = get_pos()
    
    print(f"\n{'='*80}")
    print(f"FIXED PARALLEL SCRAPER: {START} → {END}")
    print(f"{'='*80}")
    print(f"Start Position: {start_pos}")
    print(f"Workers: {WORKERS}")
    print(f"Total to scrape: {END - start_pos + 1:,}")
    print(f"⚠️  VERIFYING ALL FILES ARE ACTUALLY WRITTEN TO DISK")
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
            
            print(f"[Batch {batch_num:4d}] Cases {batch_start:7d}-{cur-1:7d} ({len(batch_cases)} submitted)... ", end="", flush=True)
            
            # Process results
            batch_found = 0
            batch_empty = 0
            batch_errors = 0
            
            for f in as_completed(futures):
                case, found, yr, is_empty = f.result()
                
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
                        print(f"\n⚠️  STOPPING: {consecutive_empty} consecutive missing results")
                        return finalize(found_count, missing_count, error_count, gap_log)
                    
                    save_pos(case + 1)
                
                else:
                    error_count += 1
                    batch_errors += 1
                    consecutive_empty = 0
                    save_pos(case + 1)
            
            print(f"✓ {batch_found} found (✓✓✓ VERIFIED SAVED) , {batch_empty} missing, {batch_errors} errors")
            
            if batch_num % 5 == 0:
                print(f"  📊 Total: {found_count:,} found (VERIFIED), {missing_count:,} missing, {error_count} errors")
                print(f"  Position: {cur:,} / {END:,} ({100*(cur-START)/(END-START+1):.1f}%)\n")
    
    return finalize(found_count, missing_count, error_count, gap_log)

def finalize(found, missing, errors, gaps):
    """Print final report"""
    total = found + missing
    
    print(f"\n{'='*80}")
    print(f"SCRAPE COMPLETE")
    print(f"{'='*80}\n")
    
    print(f"✅ Found (VERIFIED SAVED): {found:,}")
    print(f"❌ Missing: {missing:,}")
    print(f"⚠️  Errors: {errors}")
    if total > 0:
        print(f"📊 Coverage: {100*found/(found+missing):.1f}%")
    print(f"\n🔍 Gaps: {len(gaps)}")
    
    if gaps:
        print("\nFirst 20 gaps:")
        for start, end, size in gaps[:20]:
            print(f"   {start:7d} - {end:7d}: {size:6,d} cases")
        if len(gaps) > 20:
            print(f"   ... and {len(gaps)-20} more")
    
    # Verify file counts match
    print(f"\n📁 FILE VERIFICATION:")
    counts = {"2023": 0, "2024": 0, "2025": 0}
    for yr in [2023, 2024, 2025]:
        yr_dir = Path(f"out/{yr}")
        if yr_dir.exists():
            counts[str(yr)] = len(list(yr_dir.glob("*.json")))
    
    print(f"  2023: {counts['2023']} files")
    print(f"  2024: {counts['2024']} files")
    print(f"  2025: {counts['2025']} files")
    print(f"  Total: {sum(counts.values())} files")
    print(f"  Expected from scraper: {found} cases")
    
    # Save log
    with open("SCRAPE_677500_707148_LOG.txt", "w") as f:
        f.write(f"PARALLEL SCRAPE RESULTS (WITH FILE VERIFICATION)\n")
        f.write(f"Range: {START} → {END}\n")
        f.write(f"Workers: {WORKERS}\n")
        f.write(f"{'='*80}\n\n")
        f.write(f"Found (VERIFIED SAVED): {found}\n")
        f.write(f"Missing: {missing}\n")
        f.write(f"Errors: {errors}\n\n")
        f.write(f"GAPS:\n")
        for start, end, size in gaps:
            f.write(f"{start} - {end}: {size}\n")
    
    print(f"\n📋 Log: SCRAPE_677500_707148_LOG.txt")
    print(f"⏱️  Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

if __name__ == "__main__":
    main()
