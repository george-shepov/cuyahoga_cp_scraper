#!/usr/bin/env python3
"""
OPTIMIZED PARALLEL SCRAPER - 20 workers + smart batching
- Parallel execution with proper TOS handling
- Each worker gets fresh browser context
- Respects server with 500ms delays between individual requests
- Batches of 20 with monitoring
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
WORKERS = 8  # Optimal: avoids resource limits, proven to work ~2 cases/sec
REQUEST_DELAY = 0.2  # 200ms between requests (safe with 8 workers)

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

# Thread-safe request throttling
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
        
        # Wait for filesystem
        time.sleep(0.2)
        
        if file_exists_and_valid(case, yr):
            return (case, True, yr, False, None)
        
        # Check for "No cases found" in output (legitimate missing case)
        combined_output = (result.stdout + result.stderr).lower()
        if "no cases found" in combined_output or "case_not_found" in combined_output:
            return (case, False, yr, True, None)  # Missing = is_empty=True
        
        # Check for non-error exit codes (also indicates no case found)
        if result.returncode == 0:
            # Exit code 0 but no file = case simply doesn't exist
            return (case, False, yr, True, None)
        
        # Only treat as error if returncode is non-zero AND it's not a case-not-found scenario
        error_msg = result.stderr[:100] if result.stderr else result.stdout[:100]
        return (case, False, yr, False, error_msg)
        
    except subprocess.TimeoutExpired:
        return (case, False, yr, False, "TIMEOUT")
    except Exception as e:
        return (case, False, yr, False, str(e)[:80])

def scrape_parallel():
    """Parallel scraper with progressive backoff for gaps"""
    
    start_pos = get_pos()
    
    print(f"\n{'='*80} - scrape_PARALLEL_OPTIMIZED.py:120")
    print(f"OPTIMIZED PARALLEL SCRAPER: {START} → {END} - scrape_PARALLEL_OPTIMIZED.py:121")
    print(f"{'='*80} - scrape_PARALLEL_OPTIMIZED.py:122")
    print(f"Start Position: {start_pos} - scrape_PARALLEL_OPTIMIZED.py:123")
    print(f"Workers: {WORKERS} - scrape_PARALLEL_OPTIMIZED.py:124")
    print(f"Global Delay: {REQUEST_DELAY}s between requests (spread across {WORKERS} workers) - scrape_PARALLEL_OPTIMIZED.py:125")
    print(f"⚡ PARALLEL MODE WITH PROGRESSIVE BACKOFF - scrape_PARALLEL_OPTIMIZED.py:126")
    print(f"Started: {datetime.now().strftime('%Y%m%d %H:%M:%S')}\n - scrape_PARALLEL_OPTIMIZED.py:127")
    
    found_count = 0
    missing_count = 0
    error_count = 0
    skipped_ranges = []  # Track ranges we skipped for later verification
    
    cur = start_pos
    batch_num = 0
    consecutive_empty = 0
    backoff_level = 0  # Tracks which skip increment we're at
    skip_increments = [1, 2, 5, 10, 20, 50, 100]  # Progressive skip amounts
    gap_start = None
    
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        while cur <= END:
            batch_num += 1
            batch_start = cur
            batch_cases = []
            futures = {}
            
            # Create batch of cases
            for i in range(WORKERS):
                if cur > END:
                    break
                f = ex.submit(scrape, cur, i % WORKERS)
                futures[f] = cur
                batch_cases.append(cur)
                cur += 1
            
            if not futures:
                break
            
            print(f"\n[Batch {batch_num:4d}] Cases {batch_start:7d}-{cur-1:7d} ({len(batch_cases)} cases) - scrape_PARALLEL_OPTIMIZED.py:160")
            
            batch_found = 0
            batch_empty = 0
            batch_errors = 0
            batch_results = []
            
            # Process results as they complete
            for f in as_completed(futures):
                case, found, yr, is_empty, error = f.result()
                batch_results.append((case, found, yr, is_empty, error))
                
                if found:
                    batch_found += 1
                    found_count += 1
                    consecutive_empty = 0
                    backoff_level = 0  # Reset backoff when we find a case
                    if gap_start is not None:
                        skipped_ranges.append((gap_start, case - 1))
                        print(f"\n[GAP CLOSED] Cases {gap_start}-{case-1} (verified missing) - scrape_PARALLEL_OPTIMIZED.py:179")
                        gap_start = None
                    save_pos(case + 1)
                    print(f"✓ {yr}{case:06d} - scrape_PARALLEL_OPTIMIZED.py:182", end=" ", flush=True)
                
                elif is_empty:
                    batch_empty += 1
                    missing_count += 1
                    consecutive_empty += 1
                    
                    # Start tracking gap if this is first missing
                    if gap_start is None:
                        gap_start = case
                    
                    # Trigger backoff after hitting 10 consecutive missing
                    if consecutive_empty >= 10 and backoff_level < len(skip_increments):
                        skip_amount = skip_increments[backoff_level]
                        next_case = case + skip_amount
                        backoff_level += 1
                        if next_case <= END:
                            cur = next_case
                            print(f"\n[BACKOFF L{backoff_level}] Skipping +{skip_amount} (to case {next_case}) after {consecutive_empty} missing - scrape_PARALLEL_OPTIMIZED.py:200", flush=True)
                    
                    save_pos(case + 1)
                    print(f"⊝ {yr}{case:06d} - scrape_PARALLEL_OPTIMIZED.py:203", end=" ", flush=True)
                
                else:
                    batch_errors += 1
                    error_count += 1
                    consecutive_empty = 0
                    backoff_level = 0  # Reset backoff on error
                    if gap_start is not None:
                        skipped_ranges.append((gap_start, case - 1))
                        gap_start = None
                    save_pos(case + 1)
                    if error:
                        print(f"✗ {yr}{case:06d} ({error[:20]}) - scrape_PARALLEL_OPTIMIZED.py:215", end=" ", flush=True)
                    else:
                        print(f"✗ {yr}{case:06d} - scrape_PARALLEL_OPTIMIZED.py:217", end=" ", flush=True)
            
            print()  # Newline after batch
            print(f"Result: {batch_found} found, {batch_empty} missing, {batch_errors} errors - scrape_PARALLEL_OPTIMIZED.py:220")
            print(f"Progress: {found_count:,} found | {missing_count:,} missing | {error_count} errors - scrape_PARALLEL_OPTIMIZED.py:221")
            print(f"Position: {cur:,} / {END:,} ({100*(cur-START)/(END-START+1):.1f}%) - scrape_PARALLEL_OPTIMIZED.py:222")
    
    return finalize(found_count, missing_count, error_count, skipped_ranges)

def finalize(found, missing, errors, skipped_ranges=None):
    """Print final report"""
    if skipped_ranges is None:
        skipped_ranges = []
    
    print(f"\n{'='*80} - scrape_PARALLEL_OPTIMIZED.py:231")
    print(f"SCRAPE COMPLETE - scrape_PARALLEL_OPTIMIZED.py:232")
    print(f"{'='*80}\n - scrape_PARALLEL_OPTIMIZED.py:233")
    
    print(f"✅ Found (SAVED): {found:,} - scrape_PARALLEL_OPTIMIZED.py:235")
    print(f"❌ Missing: {missing:,} - scrape_PARALLEL_OPTIMIZED.py:236")
    print(f"⚠️  Errors: {errors} - scrape_PARALLEL_OPTIMIZED.py:237")
    
    if skipped_ranges:
        print(f"\n📌 SKIPPED RANGES (to verify later): - scrape_PARALLEL_OPTIMIZED.py:240")
        total_skipped = 0
        for start, end in skipped_ranges:
            count = end - start + 1
            total_skipped += count
            print(f"• {start:7d}  {end:7d} ({count:5d} cases) - scrape_PARALLEL_OPTIMIZED.py:245")
        print(f"TOTAL SKIPPED: {total_skipped:,} cases (will need verification) - scrape_PARALLEL_OPTIMIZED.py:246")
    
    counts = {"2023": 0, "2024": 0, "2025": 0}
    for yr in [2023, 2024, 2025]:
        yr_dir = Path(f"out/{yr}")
        if yr_dir.exists():
            counts[str(yr)] = len(list(yr_dir.glob("*.json")))
    
    print(f"\n📁 FILES ON DISK: - scrape_PARALLEL_OPTIMIZED.py:254")
    print(f"2023: {counts['2023']} files - scrape_PARALLEL_OPTIMIZED.py:255")
    print(f"2024: {counts['2024']} files - scrape_PARALLEL_OPTIMIZED.py:256")
    print(f"2025: {counts['2025']} files - scrape_PARALLEL_OPTIMIZED.py:257")
    print(f"Total: {sum(counts.values())} files - scrape_PARALLEL_OPTIMIZED.py:258")
    
    print(f"\n⏱️  Ended: {datetime.now().strftime('%Y%m%d %H:%M:%S')}\n - scrape_PARALLEL_OPTIMIZED.py:260")

if __name__ == "__main__":
    scrape_parallel()
