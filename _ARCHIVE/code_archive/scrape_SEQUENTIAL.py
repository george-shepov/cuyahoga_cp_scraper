#!/usr/bin/env python3
"""
SEQUENTIAL SCRAPER - One case at a time, fully loaded before next
- Forces waiting for each page to load completely
- Handles TOS properly by going back to search page
- Respects server by not hammering with parallel requests
- 2-3 second delay between requests
"""
import subprocess
import sys
import json
import time
from pathlib import Path
from datetime import datetime

RESUME = Path("scrape_677500_707148_resume.txt")
START = 677500
END = 707148
REQUEST_DELAY = 3  # 3 seconds between requests - be respectful to server

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

def scrape_sequential():
    """Scrape cases one at a time, fully waiting for each"""
    
    start_pos = get_pos()
    
    print(f"\n{'='*80}")
    print(f"SEQUENTIAL SCRAPER: {START} → {END}")
    print(f"{'='*80}")
    print(f"Start Position: {start_pos}")
    print(f"Delay between requests: {REQUEST_DELAY} seconds")
    print(f"⚠️  SEQUENTIAL - ONE CASE AT A TIME - SERVER FRIENDLY")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    found_count = 0
    missing_count = 0
    error_count = 0
    
    cur = start_pos
    case_num = 1
    consecutive_empty = 0
    MAX_CONSECUTIVE_EMPTY = 100  # Give it 100 consecutive missing before stopping
    
    while cur <= END:
        yr = get_year(cur)
        
        print(f"\n[{case_num:05d}] Scraping {yr}-{cur:06d}...", flush=True)
        
        # Call main.py with verbose output capture
        try:
            result = subprocess.run(
                ["python3", "main.py", "scrape", "--year", str(yr), 
                 "--start", str(cur), "--limit", "1", "--direction", "up"],
                capture_output=True, timeout=120, text=True
            )
            
            # Wait a bit for filesystem to settle
            time.sleep(0.5)
            
            if file_exists_and_valid(cur, yr):
                print(f"  ✓ {yr}-{cur:06d} SAVED TO DISK", flush=True)
                found_count += 1
                consecutive_empty = 0
            elif "No cases found" in result.stdout or "No cases found" in result.stderr:
                print(f"  ⊝ {yr}-{cur:06d} missing (case not found)", flush=True)
                missing_count += 1
                consecutive_empty += 1
            else:
                print(f"  ✗ {yr}-{cur:06d} error", flush=True)
                if result.stderr:
                    print(f"    stderr: {result.stderr[:100]}", flush=True)
                if result.stdout:
                    print(f"    stdout: {result.stdout[:100]}", flush=True)
                error_count += 1
                consecutive_empty = 0
            
            # Check for too many consecutive missing
            if consecutive_empty >= MAX_CONSECUTIVE_EMPTY:
                print(f"\n⚠️  STOPPING: {consecutive_empty} consecutive missing cases")
                print(f"  (Likely reached end of data for year {yr})\n")
                break
            
            # Progress update
            total_processed = found_count + missing_count + error_count
            success_rate = (100 * found_count / total_processed) if total_processed > 0 else 0
            print(f"  Progress: {found_count} found | {missing_count} missing | {error_count} errors | {success_rate:.1f}% success")
            print(f"  Position: {cur} / {END} ({100*(cur-START)/(END-START+1):.1f}%)")
            
        except subprocess.TimeoutExpired:
            print(f"  ✗ TIMEOUT (main.py took >120s)", flush=True)
            error_count += 1
            consecutive_empty = 0
        except Exception as e:
            print(f"  ✗ EXCEPTION: {str(e)[:80]}", flush=True)
            error_count += 1
            consecutive_empty = 0
        
        # Save progress
        save_pos(cur + 1)
        
        # Respectful delay before next request
        time.sleep(REQUEST_DELAY)
        
        cur += 1
        case_num += 1
    
    # Final report
    print(f"\n{'='*80}")
    print(f"SCRAPE COMPLETE")
    print(f"{'='*80}\n")
    
    print(f"✅ Found (SAVED): {found_count:,}")
    print(f"❌ Missing: {missing_count:,}")
    print(f"⚠️  Errors: {error_count}")
    
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
    
    with open("SCRAPE_SEQUENTIAL_LOG.txt", "w") as f:
        f.write(f"SEQUENTIAL SCRAPE\n")
        f.write(f"Found: {found_count}\nMissing: {missing_count}\nErrors: {error_count}\n")
        f.write(f"Range: {START} to {END}\n")
    
    print(f"\n⏱️  Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

if __name__ == "__main__":
    scrape_sequential()
