#!/usr/bin/env python3
"""
Parallel downloader - start 677500, go to TODAY with 15 workers
Downloads 15 cases simultaneously to speed up dramatically
"""
import subprocess
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from datetime import datetime
import time

RESUME_FILE = Path("parallel_resume.txt")
progress_lock = Lock()
success_count = 0
fail_count = 0
total_processed = 0

def get_case_range():
    """Calculate range: 677500 to TODAY"""
    start = 677500
    # Approximate end case (based on ~1000+ cases per day in 2025)
    # Nov 9 2025 = roughly case 707500 (ballpark)
    end = 710000  # Conservative upper bound
    return start, end

def get_resume_position():
    """Get last successful position"""
    if RESUME_FILE.exists():
        try:
            return int(RESUME_FILE.read_text().strip())
        except:
            pass
    return get_case_range()[0]

def save_position(num):
    """Thread-safe position save"""
    with progress_lock:
        RESUME_FILE.write_text(str(num))

def determine_year(case_num):
    """Determine year and normalized number"""
    if case_num <= 750000:
        return 2023, case_num
    elif case_num <= 999999:
        return 2024, case_num
    else:
        return 2025, case_num - 1000000

def scrape_single_case(case_num):
    """Scrape ONE case - called by worker thread"""
    global success_count, fail_count, total_processed
    
    year, norm_num = determine_year(case_num)
    
    try:
        result = subprocess.run([
            "python3", "main.py", "scrape",
            "--year", str(year),
            "--start", str(norm_num),
            "--limit", "1",
            "--direction", "up"
        ], capture_output=True, timeout=120, text=True)
        
        with progress_lock:
            if result.returncode == 0:
                success_count += 1
                status = "✓"
            else:
                fail_count += 1
                status = "✗"
            total_processed += 1
            
            # Print progress every 15 cases
            if total_processed % 15 == 0:
                print(f"[{total_processed:6d}] Success: {success_count} | Failed: {fail_count} | Rate: {success_count*100/(success_count+fail_count):.1f}% - parallel_download.py:77")
        
        # Save position after each successful case
        if result.returncode == 0:
            save_position(case_num)
        
        return (case_num, status)
    
    except subprocess.TimeoutExpired:
        with progress_lock:
            fail_count += 1
            total_processed += 1
        return (case_num, "⏱")
    except Exception as e:
        with progress_lock:
            fail_count += 1
            total_processed += 1
        return (case_num, "✗")

def main():
    start, end = get_case_range()
    resume_pos = get_resume_position()

    total_cases = end - start + 1

    print(f"╔════════════════════════════════════════════════════════════╗ - parallel_download.py:102")
    print(f"║  PARALLEL CASE DOWNLOADER  15 WORKERS                     ║ - parallel_download.py:103")
    print(f"║  Range: {start:7d} → {end:7d}  ({total_cases:,} cases) - parallel_download.py:104")
    print(f"║  Resuming from: {resume_pos:7d} - parallel_download.py:105")
    print(f"║  Workers: 15 parallel threads                               ║ - parallel_download.py:106")
    print(f"║  Start time: {datetime.now().strftime('%Y%m%d %H:%M:%S')}                    ║ - parallel_download.py:107")
    print(f"╚════════════════════════════════════════════════════════════╝ - parallel_download.py:108")
    
    # Generate all case numbers
    if resume_pos > start:
        cases = list(range(resume_pos, end + 1))
        print(f"Resuming from {resume_pos} ({len(cases):,} cases remaining)\n - parallel_download.py:113")
    else:
        cases = list(range(start, end + 1))
        print(f"Starting fresh ({len(cases):,} cases total)\n - parallel_download.py:116")
    
    # Run with 15 parallel workers
    with ThreadPoolExecutor(max_workers=15) as executor:
        # Submit all tasks
        futures = {executor.submit(scrape_single_case, case_num): case_num for case_num in cases}
        
        # Process results as they complete
        completed = 0
        for future in as_completed(futures):
            completed += 1
            case_num, status = future.result()
            
            # Print individual results for first 50 and last 50, sample the rest
            if completed <= 50 or completed % 100 == 0 or completed == len(cases):
                year, norm_num = determine_year(case_num)
                print(f"Case {case_num:7d} [{year}] {status} - parallel_download.py:132")
        
        print(f"\n╔════════════════════════════════════════════════════════════╗ - parallel_download.py:134")
        print(f"║  DOWNLOAD COMPLETE                                         ║ - parallel_download.py:135")
        print(f"║  Total processed: {total_processed:,}                         ║ - parallel_download.py:136")
        print(f"║  Success: {success_count:,}  |  Failed: {fail_count:,}                       ║ - parallel_download.py:137")
        rate = (success_count * 100 / (success_count + fail_count)) if (success_count + fail_count) > 0 else 0.0
        print(f"║  Success rate: {rate:.1f}%                                      ║ - parallel_download.py:139")
        print(f"║  End time: {datetime.now().strftime('%Y%m%d %H:%M:%S')}                    ║ - parallel_download.py:140")
        print(f"╚════════════════════════════════════════════════════════════╝ - parallel_download.py:141")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n⏸ PAUSED  Run again to resume from {get_resume_position()} - parallel_download.py:147")
        sys.exit(0)
