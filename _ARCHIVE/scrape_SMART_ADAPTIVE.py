#!/usr/bin/env python3
"""
SMART ADAPTIVE SCRAPER - 10 threads with intelligent throttling
- Measures actual response times and adjusts delays
- Downloads all remaining 2023, 2024, and 2025 cases
- Skips already downloaded files
- Progressive backoff for gaps
"""
import json
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
import threading
from collections import deque

# Configuration
WORKERS = 10
BATCH_SIZE = 200
MIN_DELAY = 0.15  # Minimum 150ms between requests
MAX_DELAY = 0.50  # Maximum 500ms between requests
TARGET_RESPONSE_TIME = 3.0  # Target 3 seconds per request

# Ranges to scrape
RANGES = [
    (677500, 707148, "main_range"),  # Main range covering all years
]

# Global metrics
response_times = deque(maxlen=50)  # Last 50 response times
delay_lock = threading.Lock()
current_delay = MIN_DELAY

class ResumeTracker:
    def __init__(self, resume_file):
        self.resume_file = Path(resume_file)
        self.lock = threading.Lock()
    
    def get_position(self, start):
        if self.resume_file.exists():
            try:
                pos = int(self.resume_file.read_text().strip())
                return pos if pos >= start else start
            except:
                pass
        return start
    
    def save_position(self, pos):
        with self.lock:
            self.resume_file.write_text(str(pos))

def get_year(case):
    if case < 695000:
        return 2023
    elif case < 700000:
        return 2024
    else:
        return 2025

def file_exists_and_valid(case, yr):
    """Check if file already exists and is valid"""
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

def adjust_delay(response_time):
    """Dynamically adjust delay based on response time"""
    global current_delay
    
    with delay_lock:
        response_times.append(response_time)
        
        if len(response_times) >= 10:
            avg_time = sum(response_times) / len(response_times)
            
            # If responses are fast, reduce delay
            if avg_time < TARGET_RESPONSE_TIME * 0.8:
                current_delay = max(MIN_DELAY, current_delay * 0.95)
            # If responses are slow, increase delay
            elif avg_time > TARGET_RESPONSE_TIME * 1.2:
                current_delay = min(MAX_DELAY, current_delay * 1.05)
        
        return current_delay

def scrape_case(case):
    """Scrape a single case with timing"""
    yr = get_year(case)
    
    # Skip if already exists
    if file_exists_and_valid(case, yr):
        return (case, True, False, 0, True)  # found, not_empty, time, skipped
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            ["python3", "main.py", "scrape", "--year", str(yr), 
             "--start", str(case), "--limit", "1", "--direction", "up"],
            capture_output=True, timeout=30, text=True
        )
        
        elapsed = time.time() - start_time
        adjust_delay(elapsed)
        
        # Wait for file to be written
        time.sleep(0.1)
        
        if file_exists_and_valid(case, yr):
            return (case, True, False, elapsed, False)
        
        if "No cases found" in result.stdout.lower() or "No cases found" in result.stderr.lower():
            return (case, False, True, elapsed, False)
        
        return (case, False, False, elapsed, False)
    
    except subprocess.TimeoutExpired:
        return (case, False, False, 30.0, False)
    except Exception as e:
        return (case, False, False, 0, False)

def scrape_range(start, end, name):
    """Scrape a range with adaptive threading"""
    resume = ResumeTracker(f"scrape_{name}_resume.txt")
    start_pos = resume.get_position(start)
    
    print(f"\n{'='*80} - scrape_SMART_ADAPTIVE.py:141")
    print(f"SMART ADAPTIVE SCRAPER: {start:,} → {end:,} - scrape_SMART_ADAPTIVE.py:142")
    print(f"Range: {name} - scrape_SMART_ADAPTIVE.py:143")
    print(f"{'='*80} - scrape_SMART_ADAPTIVE.py:144")
    print(f"Start Position: {start_pos:,} - scrape_SMART_ADAPTIVE.py:145")
    print(f"Workers: {WORKERS} - scrape_SMART_ADAPTIVE.py:146")
    print(f"Adaptive Delay: {MIN_DELAY}s  {MAX_DELAY}s - scrape_SMART_ADAPTIVE.py:147")
    print(f"Started: {datetime.now().strftime('%Y%m%d %H:%M:%S')}\n - scrape_SMART_ADAPTIVE.py:148")
    
    found_count = 0
    missing_count = 0
    skipped_count = 0
    batch_num = 0
    consecutive_empty = 0
    
    cur = start_pos
    
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        while cur <= end:
            batch_num += 1
            batch_start = cur
            batch_end = min(end, cur + BATCH_SIZE - 1)
            batch_cases = list(range(cur, batch_end + 1))
            
            if not batch_cases:
                break
            
            print(f"\n[Batch {batch_num:4d}] Cases {batch_start:,} → {batch_end:,} ({len(batch_cases)} tasks) [Delay: {current_delay:.3f}s] - scrape_SMART_ADAPTIVE.py:168")
            
            batch_found = 0
            batch_empty = 0
            batch_skipped = 0
            batch_times = []
            
            # Submit tasks with current delay
            futures = {}
            for case in batch_cases:
                time.sleep(current_delay)
                future = executor.submit(scrape_case, case)
                futures[future] = case
            
            # Process results as they complete
            for future in as_completed(futures):
                try:
                    case, found, is_empty, response_time, skipped = future.result()
                    
                    if response_time > 0:
                        batch_times.append(response_time)
                    
                    if skipped:
                        batch_skipped += 1
                        skipped_count += 1
                        consecutive_empty = 0
                        resume.save_position(case + 1)
                        print("S - scrape_SMART_ADAPTIVE.py:195", end="", flush=True)
                    
                    elif found:
                        batch_found += 1
                        found_count += 1
                        consecutive_empty = 0
                        resume.save_position(case + 1)
                        print("✓ - scrape_SMART_ADAPTIVE.py:202", end="", flush=True)
                    
                    elif is_empty:
                        batch_empty += 1
                        missing_count += 1
                        consecutive_empty += 1
                        resume.save_position(case + 1)
                        print("⊝ - scrape_SMART_ADAPTIVE.py:209", end="", flush=True)
                        
                        if consecutive_empty >= 100:
                            print(f"\n\n⚠️  Stopping: {consecutive_empty} consecutive missing - scrape_SMART_ADAPTIVE.py:212")
                            return finalize(found_count, missing_count, skipped_count, name)
                    else:
                        consecutive_empty = 0
                        resume.save_position(case + 1)
                        print("✗ - scrape_SMART_ADAPTIVE.py:217", end="", flush=True)
                
                except Exception as e:
                    print("E - scrape_SMART_ADAPTIVE.py:220", end="", flush=True)
            
            print()
            
            # Show batch stats
            avg_time = sum(batch_times) / len(batch_times) if batch_times else 0
            print(f"Result: {batch_found} found, {batch_skipped} skipped, {batch_empty} missing - scrape_SMART_ADAPTIVE.py:226")
            print(f"Performance: Avg {avg_time:.2f}s/request, Delay {current_delay:.3f}s - scrape_SMART_ADAPTIVE.py:227")
            print(f"Progress: {found_count:,} found | {skipped_count:,} skipped | {missing_count:,} missing - scrape_SMART_ADAPTIVE.py:228")
            pct = 100 * (cur - start) / (end - start + 1)
            print(f"Position: {cur:,} / {end:,} ({pct:.1f}%) - scrape_SMART_ADAPTIVE.py:230")
            
            cur = batch_end + 1
    
    return finalize(found_count, missing_count, skipped_count, name)

def finalize(found, missing, skipped, name):
    """Print final report"""
    print(f"\n{'='*80} - scrape_SMART_ADAPTIVE.py:238")
    print(f"SCRAPE COMPLETE: {name} - scrape_SMART_ADAPTIVE.py:239")
    print(f"{'='*80}\n - scrape_SMART_ADAPTIVE.py:240")
    
    print(f"✅ Found (NEW): {found:,} - scrape_SMART_ADAPTIVE.py:242")
    print(f"⏭️  Skipped (EXISTS): {skipped:,} - scrape_SMART_ADAPTIVE.py:243")
    print(f"❌ Missing: {missing:,} - scrape_SMART_ADAPTIVE.py:244")
    
    counts = {"2023": 0, "2024": 0, "2025": 0}
    for yr in [2023, 2024, 2025]:
        yr_dir = Path(f"out/{yr}")
        if yr_dir.exists():
            counts[str(yr)] = len(list(yr_dir.glob("*.json")))
    
    print(f"\n📁 TOTAL FILES ON DISK: - scrape_SMART_ADAPTIVE.py:252")
    print(f"2023: {counts['2023']:,} files - scrape_SMART_ADAPTIVE.py:253")
    print(f"2024: {counts['2024']:,} files - scrape_SMART_ADAPTIVE.py:254")
    print(f"2025: {counts['2025']:,} files - scrape_SMART_ADAPTIVE.py:255")
    print(f"TOTAL: {sum(counts.values()):,} files - scrape_SMART_ADAPTIVE.py:256")
    
    print(f"\n⏱️  Ended: {datetime.now().strftime('%Y%m%d %H:%M:%S')}\n - scrape_SMART_ADAPTIVE.py:258")

if __name__ == "__main__":
    for start, end, name in RANGES:
        scrape_range(start, end, name)
