#!/usr/bin/env python3
"""
OPTIMIZED PARALLEL SCRAPER - 12 workers
- Parallel execution with proper TOS handling
- Each worker gets fresh browser context
- Respects server with delays between requests
- Batches with monitoring
- Verifies all files saved to disk
"""
import subprocess
import sys
import json
import time
import threading
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

RESUME = Path("scrape_677500_707148_PARALLEL_resume.txt")
START = 677500
END = 707148
WORKERS = 12
REQUEST_DELAY = 0.15

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

request_times = {}
request_lock = threading.Lock()

def throttle_request(worker_id):
    """Throttle requests globally to be nice to server"""
    global request_times
    with request_lock:
        now = time.time()
        min_time = now + REQUEST_DELAY
        time.sleep(REQUEST_DELAY)

def scrape(case, worker_id):
    """Scrape single case with throttling"""
    throttle_request(worker_id)
    
    yr = get_year(case)
    try:
        result = subprocess.run(
            ["python3", "main.py", "scrape", "--year", str(yr), 
             "--start", str(case), "--limit", "1", "--direction", "up"],
            capture_output=True, timeout=180, text=True
        )
        
        time.sleep(0.2)
        
        if file_exists_and_valid(case, yr):
            return (case, True, yr, False, None)
        
        if "No cases found" in result.stdout.lower() or "No cases found" in result.stderr.lower():
            return (case, False, yr, True, None)
        
        error_msg = result.stderr[:100] if result.stderr else result.stdout[:100]
        return (case, False, yr, False, error_msg)
        
    except subprocess.TimeoutExpired:
        return (case, False, yr, False, "TIMEOUT")
    except Exception as e:
        return (case, False, yr, False, str(e)[:80])

def scrape_parallel():
    """Parallel scraper with batching"""
    
    start_pos = get_pos()
    
    print(f"\n{'='*80}")
    print(f"OPTIMIZED PARALLEL SCRAPER: {START} → {END}")
    print(f"{'='*80}")
    print(f"Start Position: {start_pos}")
    print(f"Workers: {WORKERS}")
    print(f"Global Delay: {REQUEST_DELAY}s between requests")
    print(f"⚡ PARALLEL MODE - MASSIVELY FASTER")
    print(f"Started: {datetime.now().strftime('%Y%m%d %H:%M:%S')}\n")
    
    found_count = 0
    missing_count = 0
    error_count = 0
    
    cur = start_pos
    batch_num = 0
    consecutive_empty = 0
    MAX_CONSECUTIVE_EMPTY = 100
    
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        while cur <= END:
            batch_num += 1
            batch_start = cur
            batch_cases = []
            futures = {}
            
            for i in range(WORKERS):
                if cur > END:
                    break
                f = ex.submit(scrape, cur, i % WORKERS)
                futures[f] = cur
                batch_cases.append(cur)
                cur += 1
            
            if not futures:
                break
            
            print(f"\n[Batch {batch_num:4d}] Cases {batch_start:7d}-{cur-1:7d} ({len(batch_cases)} cases)")
            
            batch_found = 0
            batch_empty = 0
            batch_errors = 0
            batch_results = []
            
            for f in as_completed(futures):
                case, found, yr, is_empty, error = f.result()
                batch_results.append((case, found, yr, is_empty, error))
                
                if found:
                    batch_found += 1
                    found_count += 1
                    consecutive_empty = 0
                    save_pos(case + 1)
                    print(f"✓ {yr}{case:06d}", end=" ", flush=True)
                
                elif is_empty:
                    batch_empty += 1
                    missing_count += 1
                    consecutive_empty += 1
                    save_pos(case + 1)
                    print(f"⊝ {yr}{case:06d}", end=" ", flush=True)
                    
                    if consecutive_empty >= MAX_CONSECUTIVE_EMPTY:
                        print(f"\n\n⚠️  STOPPING: {consecutive_empty} consecutive missing")
                        return finalize(found_count, missing_count, error_count)
                
                else:
                    batch_errors += 1
                    error_count += 1
                    consecutive_empty = 0
                    save_pos(case + 1)
                    if error:
                        print(f"✗ {yr}{case:06d} ({error[:20]})", end=" ", flush=True)
                    else:
                        print(f"✗ {yr}{case:06d}", end=" ", flush=True)
            
            print()
            print(f"Result: {batch_found} found, {batch_empty} missing, {batch_errors} errors")
            print(f"Progress: {found_count:,} found | {missing_count:,} missing | {error_count} errors")
            print(f"Position: {cur:,} / {END:,} ({100*(cur-START)/(END-START+1):.1f}%)")
    
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
    print(f"2023: {counts['2023']} files")
    print(f"2024: {counts['2024']} files")
    print(f"2025: {counts['2025']} files")
    print(f"Total: {sum(counts.values())} files")
    
    print(f"\n⏱️  Ended: {datetime.now().strftime('%Y%m%d %H:%M:%S')}\n")

if __name__ == "__main__":
    scrape_parallel()
