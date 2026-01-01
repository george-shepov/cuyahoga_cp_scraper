#!/usr/bin/env python3
"""
Continuous scraper that never stops:
1. Downloads all cases from MIN to current highest case number
2. When done, checks for new cases every hour
3. Automatically detects year from case numbers
4. Runs in headless mode
5. Saves progress to resume if interrupted
"""
import subprocess
import sys
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

RESUME_FILE = Path("continuous_resume.txt")
MIN_CASE = 677500  # Start from this case number
MAX_CASE = 1_000_000  # Stop checking after this
WORKERS = 20  # Parallel workers (balanced: not too slow, not overwhelming)
CHECK_INTERVAL = 3600  # Check for new cases every hour (3600 seconds)
DELAY_BETWEEN_BATCHES = 3  # Seconds to wait between batches (be polite to server)

def get_resume_position():
    """Get last processed case number from resume file"""
    if RESUME_FILE.exists():
        try:
            return max(int(RESUME_FILE.read_text().strip()), MIN_CASE)
        except:
            pass
    return MIN_CASE

def save_resume_position(case_num):
    """Save progress to resume file"""
    RESUME_FILE.write_text(str(case_num))

def find_highest_case():
    """Find the highest case number we currently have"""
    highest = MIN_CASE
    for year_dir in Path("out").glob("20*"):
        if year_dir.is_dir():
            for json_file in year_dir.glob("*.json"):
                try:
                    # Extract case number from filename: 2023-684826_timestamp.json
                    parts = json_file.stem.split('_')[0].split('-')
                    if len(parts) >= 2:
                        case_num = int(parts[1])
                        highest = max(highest, case_num)
                except:
                    pass
    return highest

def scrape_case(case_num):
    """
    Scrape a single case using year auto-detection and download sentencing PDFs
    Returns: (case_num, success, error_msg)
    """
    try:
        # Run scraper with PDF download enabled - it will get sentencing entries
        result = subprocess.run(
            ["python3", "main.py", "scrape", "--start", str(case_num), "--limit", "1", "--headless", "--download-pdfs"],
            capture_output=True,
            timeout=180,  # Longer timeout for PDF downloads
            text=True
        )
        
        # Check if successful
        if result.returncode == 0:
            # Verify JSON was created
            for year_dir in Path("out").glob("20*"):
                pattern = f"*-{case_num:06d}_*.json"
                if list(year_dir.glob(pattern)):
                    return (case_num, True, None)
            return (case_num, False, "No JSON created")
        else:
            return (case_num, False, f"Exit code {result.returncode}")
    except subprocess.TimeoutExpired:
        return (case_num, False, "Timeout")
    except Exception as e:
        return (case_num, False, str(e))

def scrape_batch(start, end, batch_num):
    """Scrape a batch of cases in parallel"""
    cases = range(start, min(end, MAX_CASE + 1))
    
    print(f"\n[Batch {batch_num}] Cases {start}{end} ({len(list(cases))} cases) - continuous_scraper.py:87", flush=True)
    
    success_count = 0
    fail_count = 0
    
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(scrape_case, case): case for case in cases}
        
        completed = 0
        for future in as_completed(futures):
            case_num, success, error = future.result()
            completed += 1
            
            if success:
                success_count += 1
                status = "✓"
            else:
                fail_count += 1
                status = "✗"
            
            # Show progress every 10 cases
            if completed % 10 == 0:
                print(f"[{completed:4d}/{len(cases)}] {case_num:06d} {status} - continuous_scraper.py:109")
            
            # Save progress
            save_resume_position(case_num + 1)
    
    print(f"[Batch {batch_num}] Complete: {success_count} success, {fail_count} failed\n - continuous_scraper.py:114")
    return success_count, fail_count

def continuous_scrape():
    """Main continuous scraping loop"""
    print("\n - continuous_scraper.py:119" + "="*70, flush=True)
    print("🔄 CONTINUOUS SCRAPER  NEVER STOPS - continuous_scraper.py:120", flush=True)
    print("= - continuous_scraper.py:121"*70, flush=True)
    print(f"Start case: {MIN_CASE:,} - continuous_scraper.py:122", flush=True)
    print(f"Max case: {MAX_CASE:,} - continuous_scraper.py:123", flush=True)
    print(f"Workers: {WORKERS} - continuous_scraper.py:124", flush=True)
    print(f"Check interval: {CHECK_INTERVAL}s ({CHECK_INTERVAL/3600:.1f}h) - continuous_scraper.py:125", flush=True)
    print("= - continuous_scraper.py:126"*70 + "\n", flush=True)
    
    batch_num = 0
    total_success = 0
    total_fail = 0
    
    while True:
        # Get current position
        current = get_resume_position()
        highest = find_highest_case()
        
        print(f"📊 Status: Current={current:,}, Highest={highest:,} - continuous_scraper.py:137")
        
        # Determine range to scrape
        if current <= highest:
            # Still catching up
            end = min(current + WORKERS, highest + 1)
            print(f"📥 Catching up: {current:,} → {end:,} - continuous_scraper.py:143")
        else:
            # Check for new cases beyond what we have
            end = min(current + WORKERS, MAX_CASE + 1)
            print(f"🔍 Checking for new cases: {current:,} → {end:,} - continuous_scraper.py:147")
        
        if current >= MAX_CASE:
            print(f"\n✅ Reached max case {MAX_CASE:,} - continuous_scraper.py:150")
            print(f"⏰ Waiting {CHECK_INTERVAL}s before checking for new cases... - continuous_scraper.py:151")
            time.sleep(CHECK_INTERVAL)
            
            # Reset to check from highest case we have
            new_highest = find_highest_case()
            save_resume_position(new_highest + 1)
            continue
        
        # Scrape batch
        batch_num += 1
        success, fail = scrape_batch(current, end, batch_num)
        total_success += success
        total_fail += fail
        
        print(f"📈 Total: {total_success:,} success, {total_fail:,} failed - continuous_scraper.py:165")
        
        # Polite delay between batches - don't hammer the server
        time.sleep(DELAY_BETWEEN_BATCHES)

if __name__ == "__main__":
    try:
        continuous_scrape()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user - continuous_scraper.py:174")
        print(f"Resume position saved: {get_resume_position():,} - continuous_scraper.py:175")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Error: {e} - continuous_scraper.py:178")
        sys.exit(1)
