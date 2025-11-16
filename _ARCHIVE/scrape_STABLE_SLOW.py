#!/usr/bin/env python3
"""
SLOWER version with longer delays to avoid rate limiting
- 10 workers instead of 25
- 1 second delay between each request
- Longer timeout
"""
import subprocess
import sys
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

RESUME = Path("scrape_677500_707148_resume.txt")
START = 677500
END = 707148
WORKERS = 10  # Reduced to 10
REQUEST_DELAY = 2  # 2 second delay between requests

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

request_lock_time = [0.0]  # Track last request time

def scrape(case):
    """Scrape single case with delay"""
    # Enforce delay between requests
    now = time.time()
    wait = max(0.0, REQUEST_DELAY - (now - request_lock_time[0]))
    if wait > 0:
        time.sleep(wait)
    request_lock_time[0] = time.time()
    
    yr = get_year(case)
    try:
        print(f"  → Scraping {yr}-{case:06d}...", flush=True)
        
        r = subprocess.run(
            ["python3", "main.py", "scrape", "--year", str(yr), 
             "--start", str(case), "--limit", "1", "--direction", "up"],
            capture_output=True, timeout=150, text=True
        )
        
        time.sleep(0.2)  # Small delay after request
        
        if file_exists_and_valid(case, yr):
            print(f"  ✓ {yr}-{case:06d} SAVED", flush=True)
            return (case, True, yr, False)
        
        if "not found" in r.stdout.lower() or "not found" in r.stderr.lower():
            print(f"  ⊝ {yr}-{case:06d} missing", flush=True)
            return (case, False, yr, True)
        
        print(f"  ✗ {yr}-{case:06d} error", flush=True)
        return (case, False, yr, False)
    except Exception as e:
        print(f"  ✗ {yr}-{case:06d} exception", flush=True)
        return (case, False, yr, False)

def main():
    start_pos = get_pos()
    
    print(f"\n{'='*80}")
    print(f"SLOWER STABLE SCRAPER: {START} → {END}")
    print(f"{'='*80}")
    print(f"Start Position: {start_pos}")
    print(f"Workers: {WORKERS} (REDUCED for stability)")
    print(f"Request Delay: {REQUEST_DELAY} seconds between requests")
    print(f"⚠️  SLOWER BUT MORE STABLE - AVOIDING RATE LIMITS")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    found_count = 0
    missing_count = 0
    error_count = 0
    consecutive_empty = 0
    MAX_CONSECUTIVE_EMPTY = 30
    
    cur = start_pos
    batch_num = 0
    
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        while cur <= END:
            batch_num += 1
            batch_start = cur
            batch_cases = []
            futures = {}
            
            for i in range(WORKERS):
                if cur > END:
                    break
                f = ex.submit(scrape, cur)
                futures[f] = cur
                batch_cases.append(cur)
                cur += 1
            
            print(f"[Batch {batch_num:4d}] Cases {batch_start:7d}-{cur-1:7d}", flush=True)
            
            batch_found = 0
            batch_empty = 0
            batch_errors = 0
            
            for f in as_completed(futures):
                case, found, yr, is_empty = f.result()
                
                if found:
                    found_count += 1
                    batch_found += 1
                    consecutive_empty = 0
                    save_pos(case + 1)
                
                elif is_empty:
                    missing_count += 1
                    batch_empty += 1
                    consecutive_empty += 1
                    
                    if consecutive_empty >= MAX_CONSECUTIVE_EMPTY:
                        print(f"\n⚠️  STOPPING: {consecutive_empty} consecutive missing")
                        return finalize(found_count, missing_count, error_count)
                    
                    save_pos(case + 1)
                
                else:
                    error_count += 1
                    batch_errors += 1
                    consecutive_empty = 0
                    save_pos(case + 1)
            
            print(f"  Result: {batch_found} found, {batch_empty} missing, {batch_errors} errors")
            print(f"  Progress: {found_count:,} found | {missing_count:,} missing | {error_count} errors")
            print(f"  Position: {cur:,} / {END:,} ({100*(cur-START)/(END-START+1):.1f}%)\n")
    
    return finalize(found_count, missing_count, error_count)

def finalize(found, missing, errors):
    """Print final report"""
    print(f"\n{'='*80}")
    print(f"SCRAPE COMPLETE")
    print(f"{'='*80}\n")
    
    print(f"✅ Found (SAVED): {found:,}")
    print(f"❌ Missing: {missing:,}")
    print(f"⚠️  Errors: {errors}")
    
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
    
    with open("SCRAPE_677500_707148_LOG.txt", "w") as f:
        f.write(f"SLOW STABLE SCRAPE\n")
        f.write(f"Found: {found}\nMissing: {missing}\nErrors: {errors}\n")
    
    print(f"\n⏱️  Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

if __name__ == "__main__":
    main()
