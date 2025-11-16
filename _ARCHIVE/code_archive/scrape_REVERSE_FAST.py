#!/usr/bin/env python3
"""
REVERSE SCRAPER - FAST VERSION
- Start from END (707,148) and work backward to meet PARALLEL (689,835)
- 8 parallel workers, minimal throttling
- Minimal sleep between submissions (only 50ms to avoid overwhelming)
"""
import json
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess

RESUME = Path("scrape_677500_707148_REVERSE_resume.txt")
START = 707148  # Start at END
END = 689835    # Work backward to meet PARALLEL scraper
WORKERS = 8
BATCH_SIZE = 200  # Larger batches = fewer sleeps
DELAY = 0.05    # 50ms between submissions only (main.py has its own throttle)

def get_pos():
    if RESUME.exists():
        try:
            pos = int(RESUME.read_text().strip())
            if END <= pos <= START:
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

def scrape_case(case):
    """Scrape a single case - main.py handles its own throttling"""
    yr = get_year(case)
    
    try:
        result = subprocess.run(
            ["python3", "main.py", "scrape", "--year", str(yr), 
             "--start", str(case), "--limit", "1", "--direction", "up"],
            capture_output=True, timeout=180, text=True
        )
        
        # Wait for file to be written
        time.sleep(0.1)
        
        if file_exists_and_valid(case, yr):
            return (case, True, False)
        
        if "No cases found" in result.stdout.lower() or "No cases found" in result.stderr.lower():
            return (case, False, True)
        
        return (case, False, False)
    
    except Exception as e:
        return (case, False, False)

def scrape_reverse():
    """Reverse scraper: start at END, work backward"""
    
    start_pos = get_pos()
    
    print(f"\n{'='*80}")
    print(f"REVERSE SCRAPER FAST: {START} → {END} (BACKWARD)")
    print(f"{'='*80}")
    print(f"Start Position: {start_pos}")
    print(f"Target: Meet PARALLEL scraper at {END}")
    print(f"Workers: {WORKERS} parallel")
    print(f"Batch Size: {BATCH_SIZE}")
    print(f"Started: {datetime.now().strftime('%Y%m%d %H:%M:%S')}\n")
    
    found_count = 0
    missing_count = 0
    batch_num = 0
    consecutive_empty = 0
    consecutive_empty_max = 100
    
    # Work backward from start_pos to END
    cur = start_pos
    
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        while cur >= END:
            batch_num += 1
            batch_start = cur
            batch_end = max(END, cur - BATCH_SIZE + 1)
            batch_cases = list(range(cur, batch_end - 1, -1))  # Countdown
            
            if not batch_cases:
                break
            
            print(f"\n[Batch {batch_num:4d}] Cases {batch_start:7d} → {batch_end:7d} ({len(batch_cases)} tasks)")
            
            batch_found = 0
            batch_empty = 0
            
            # Submit all tasks quickly (minimal throttle)
            futures = {}
            for case in batch_cases:
                future = executor.submit(scrape_case, case)
                futures[future] = case
                time.sleep(DELAY)  # Very light throttle on submission
            
            # Process results as they complete
            for future in as_completed(futures):
                try:
                    case, found, is_empty = future.result()
                    
                    if found:
                        batch_found += 1
                        found_count += 1
                        consecutive_empty = 0
                        save_pos(case - 1)
                        print("✓", end="", flush=True)
                    
                    elif is_empty:
                        batch_empty += 1
                        missing_count += 1
                        consecutive_empty += 1
                        save_pos(case - 1)
                        print("⊝", end="", flush=True)
                        
                        if consecutive_empty >= consecutive_empty_max:
                            print(f"\n\n⚠️  Stopping: {consecutive_empty} consecutive missing cases")
                            return finalize(found_count, missing_count)
                    else:
                        consecutive_empty = 0
                        save_pos(case - 1)
                        print("✗", end="", flush=True)
                
                except Exception as e:
                    print("E", end="", flush=True)
            
            print()
            print(f"Result: {batch_found} found, {batch_empty} missing")
            print(f"Progress: {found_count:,} found | {missing_count:,} missing")
            pct = 100 * (start_pos - cur) / (start_pos - END) if (start_pos - END) > 0 else 0
            print(f"Position: {cur:,} → {END:,} ({pct:.1f}% complete)")
            
            # Move to next batch (going backward)
            cur = batch_end - 1
    
    return finalize(found_count, missing_count)

def finalize(found, missing):
    """Print final report"""
    print(f"\n{'='*80}")
    print(f"REVERSE SCRAPE COMPLETE")
    print(f"{'='*80}\n")
    
    print(f"✅ Found (SAVED): {found:,}")
    print(f"❌ Missing: {missing:,}")
    
    counts = {"2023": 0, "2024": 0, "2025": 0}
    for yr in [2023, 2024, 2025]:
        yr_dir = Path(f"out/{yr}")
        if yr_dir.exists():
            counts[str(yr)] = len(list(yr_dir.glob("*.json")))
    
    print(f"\n📁 FILES ON DISK:")
    print(f"2023: {counts['2023']} files")
    print(f"2024: {counts['2024']} files")
    print(f"2025: {counts['2025']} files")
    print(f"TOTAL: {sum(counts.values())} files")
    
    print(f"\n⏱️  Ended: {datetime.now().strftime('%Y%m%d %H:%M:%S')}\n")

if __name__ == "__main__":
    scrape_reverse()
