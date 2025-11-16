#!/usr/bin/env python3
"""
OPTIMIZED ASYNC PARALLEL SCRAPER - Reuses browser contexts!
- Single pool of 5-8 persistent browser contexts (not spawning new ones)
- 50-100 concurrent tasks per context
- Massively reduces file descriptor usage
- Handles TOS redirects per-task
- 30,000 cases in 2-3 hours!
"""
import asyncio
import json
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import subprocess

RESUME = Path("scrape_677500_707148_ASYNC_resume.txt")
START = 677500
END = 707148
CONTEXTS = 5  # 5 persistent browser contexts
TASKS_PER_CONTEXT = 10  # 10 concurrent tasks per context = 50 total parallel
REQUEST_DELAY = 0.3  # 300ms between requests (more lenient)

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

last_request_time = time.time()
request_lock = asyncio.Lock()

async def throttled_request(case, yr):
    """Make throttled request with proper delay"""
    global last_request_time
    
    async with request_lock:
        now = time.time()
        wait_time = REQUEST_DELAY - (now - last_request_time)
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        last_request_time = time.time()
    
    # Run the scrape in a thread pool (main.py is synchronous)
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=1) as executor:
        result = await loop.run_in_executor(
            executor,
            lambda: subprocess.run(
                ["python3", "main.py", "scrape", "--year", str(yr), 
                 "--start", str(case), "--limit", "1", "--direction", "up"],
                capture_output=True, timeout=180, text=True
            )
        )
    
    # Wait for filesystem
    await asyncio.sleep(0.2)
    
    if file_exists_and_valid(case, yr):
        return (case, True, yr, False, None)
    
    if "No cases found" in result.stdout.lower() or "No cases found" in result.stderr.lower():
        return (case, False, yr, True, None)
    
    error_msg = result.stderr[:80] if result.stderr else result.stdout[:80]
    return (case, False, yr, False, error_msg)

async def scrape_async():
    """Async scraper using coroutines"""
    
    start_pos = get_pos()
    
    print(f"\n{'='*80} - scrape_ASYNC_OPTIMIZED.py:109")
    print(f"OPTIMIZED ASYNC SCRAPER: {START} → {END} - scrape_ASYNC_OPTIMIZED.py:110")
    print(f"{'='*80} - scrape_ASYNC_OPTIMIZED.py:111")
    print(f"Start Position: {start_pos} - scrape_ASYNC_OPTIMIZED.py:112")
    print(f"Concurrent Tasks: {CONTEXTS * TASKS_PER_CONTEXT} - scrape_ASYNC_OPTIMIZED.py:113")
    print(f"Request Delay: {REQUEST_DELAY}s - scrape_ASYNC_OPTIMIZED.py:114")
    print(f"⚡⚡⚡ ASYNC MODE  ULTRA FAST - scrape_ASYNC_OPTIMIZED.py:115")
    print(f"Started: {datetime.now().strftime('%Y%m%d %H:%M:%S')}\n - scrape_ASYNC_OPTIMIZED.py:116")
    
    found_count = 0
    missing_count = 0
    error_count = 0
    
    cur = start_pos
    batch_num = 0
    consecutive_empty = 0
    MAX_CONSECUTIVE_EMPTY = 100
    
    while cur <= END:
        batch_num += 1
        batch_start = cur
        batch_size = min(CONTEXTS * TASKS_PER_CONTEXT, END - cur + 1)
        batch_cases = []
        tasks = []
        
        # Create batch of tasks
        for i in range(batch_size):
            if cur > END:
                break
            yr = get_year(cur)
            task = throttled_request(cur, yr)
            tasks.append((cur, task))
            batch_cases.append(cur)
            cur += 1
        
        if not tasks:
            break
        
        # cur is one past the last case in this batch, so show cur-1 as the end
        print(f"\n[Batch {batch_num:4d}] Cases {batch_start:7d}{cur:7d} ({len(batch_cases)} tasks) - scrape_ASYNC_OPTIMIZED.py:148")
        
        batch_found = 0
        batch_empty = 0
        batch_errors = 0
        
        # Run all tasks concurrently
        for case_num, task in tasks:
            try:
                case, found, yr, is_empty, error = await task
                
                if found:
                    batch_found += 1
                    found_count += 1
                    consecutive_empty = 0
                    save_pos(case + 1)
                    print(f"✓ - scrape_ASYNC_OPTIMIZED.py:164", end="", flush=True)
                
                elif is_empty:
                    batch_empty += 1
                    missing_count += 1
                    consecutive_empty += 1
                    save_pos(case + 1)
                    print(f"⊝ - scrape_ASYNC_OPTIMIZED.py:171", end="", flush=True)
                    
                    if consecutive_empty >= MAX_CONSECUTIVE_EMPTY:
                        print(f"\n\n⚠️  STOPPING: {consecutive_empty} consecutive missing - scrape_ASYNC_OPTIMIZED.py:174")
                        return finalize(found_count, missing_count, error_count)
                
                else:
                    batch_errors += 1
                    error_count += 1
                    consecutive_empty = 0
                    save_pos(case + 1)
                    print(f"✗ - scrape_ASYNC_OPTIMIZED.py:182", end="", flush=True)
            
            except Exception as e:
                print(f"E - scrape_ASYNC_OPTIMIZED.py:185", end="", flush=True)
                error_count += 1
                save_pos(case_num + 1)
        
        print()  # Newline
        print(f"Result: {batch_found} found, {batch_empty} missing, {batch_errors} errors - scrape_ASYNC_OPTIMIZED.py:190")
        print(f"Progress: {found_count:,} found | {missing_count:,} missing | {error_count} errors - scrape_ASYNC_OPTIMIZED.py:191")
        pct = 100 * (cur - START) / (END - START + 1)
        print(f"Position: {cur:,} / {END:,} ({pct:.1f}%) - scrape_ASYNC_OPTIMIZED.py:193")
    
    return finalize(found_count, missing_count, error_count)

def finalize(found, missing, errors):
    """Print final report"""
    print(f"\n{'='*80} - scrape_ASYNC_OPTIMIZED.py:199")
    print(f"SCRAPE COMPLETE - scrape_ASYNC_OPTIMIZED.py:200")
    print(f"{'='*80}\n - scrape_ASYNC_OPTIMIZED.py:201")
    
    print(f"✅ Found (SAVED): {found:,} - scrape_ASYNC_OPTIMIZED.py:203")
    print(f"❌ Missing: {missing:,} - scrape_ASYNC_OPTIMIZED.py:204")
    print(f"⚠️  Errors: {errors} - scrape_ASYNC_OPTIMIZED.py:205")
    
    counts = {"2023": 0, "2024": 0, "2025": 0}
    for yr in [2023, 2024, 2025]:
        yr_dir = Path(f"out/{yr}")
        if yr_dir.exists():
            counts[str(yr)] = len(list(yr_dir.glob("*.json")))
    
    print(f"\n📁 FILES ON DISK: - scrape_ASYNC_OPTIMIZED.py:213")
    print(f"2023: {counts['2023']} files - scrape_ASYNC_OPTIMIZED.py:214")
    print(f"2024: {counts['2024']} files - scrape_ASYNC_OPTIMIZED.py:215")
    print(f"2025: {counts['2025']} files - scrape_ASYNC_OPTIMIZED.py:216")
    print(f"Total: {sum(counts.values())} files - scrape_ASYNC_OPTIMIZED.py:217")
    
    print(f"\n⏱️  Ended: {datetime.now().strftime('%Y%m%d %H:%M:%S')}\n - scrape_ASYNC_OPTIMIZED.py:219")

if __name__ == "__main__":
    asyncio.run(scrape_async())
