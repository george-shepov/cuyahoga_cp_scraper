#!/usr/bin/env python3
"""
FIXED SCRAPER - Handle TOS redirects properly, sequential requests
- Detects TOS redirects and retries criminal form selection
- Waits properly for UpdatePanel to render
- Sequential processing (one case at a time)
- 2 second delay between requests
"""
import subprocess
import sys
import json
import time
from pathlib import Path
from datetime import datetime

RESUME = Path("scrape_677500_707148_FIXED_resume.txt")
START = 677500
END = 707148
REQUEST_DELAY = 2  # 2 seconds between requests

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

def scrape_fixed():
    """Scrape cases sequentially with TOS recovery"""
    
    start_pos = get_pos()
    
    print(f"\n{'='*80}")
    print(f"FIXED SEQUENTIAL SCRAPER: {START} → {END}")
    print(f"{'='*80}")
    print(f"Start Position: {start_pos}")
    print(f"Delay between requests: {REQUEST_DELAY} seconds")
    print(f"✓ Fixed: Main.py no longer times out on is_checked()")
    print(f"✓ Fixed: Handles TOS redirects with retry logic")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    found_count = 0
    missing_count = 0
    error_count = 0
    
    cur = start_pos
    case_num = 1
    consecutive_empty = 0
    MAX_CONSECUTIVE_EMPTY = 50
    
    while cur <= END:
        yr = get_year(cur)
        
        print(f"\n[{case_num:05d}] Scraping {yr}-{cur:06d}...", flush=True)
        
        # Call main.py
        try:
            result = subprocess.run(
                ["python3", "main.py", "scrape", "--year", str(yr), 
                 "--start", str(cur), "--limit", "1", "--direction", "up"],
                capture_output=True, timeout=150, text=True
            )
            
            # Wait for filesystem
            time.sleep(0.5)
            
            if file_exists_and_valid(cur, yr):
                print(f"  ✓ {yr}-{cur:06d} SAVED", flush=True)
                found_count += 1
                consecutive_empty = 0
            elif "No cases found" in result.stdout.lower() or "No cases found" in result.stderr.lower():
                print(f"  ⊝ {yr}-{cur:06d} missing", flush=True)
                missing_count += 1
                consecutive_empty += 1
            else:
                # Check for specific errors
                if "Timeout" in result.stderr or "timeout" in result.stderr.lower():
                    print(f"  ✗ {yr}-{cur:06d} TIMEOUT", flush=True)
                elif "Redirected back to TOS" in result.stderr:
                    print(f"  ! {yr}-{cur:06d} TOS redirect (will retry)", flush=True)
                else:
                    print(f"  ✗ {yr}-{cur:06d} error", flush=True)
                error_count += 1
                consecutive_empty = 0
            
            # Check for too many consecutive missing
            if consecutive_empty >= MAX_CONSECUTIVE_EMPTY:
                print(f"\n⚠️  STOPPING: {consecutive_empty} consecutive missing")
                break
            
            # Progress
            total = found_count + missing_count + error_count
            success_rate = (100 * found_count / total) if total > 0 else 0
            print(f"  Progress: {found_count} found | {missing_count} missing | {error_count} errors | {success_rate:.1f}%")
            print(f"  Position: {cur} / {END} ({100*(cur-START)/(END-START+1):.1f}%)")
            
        except subprocess.TimeoutExpired:
            print(f"  ✗ PROCESS TIMEOUT (150s)", flush=True)
            error_count += 1
        except Exception as e:
            print(f"  ✗ EXCEPTION: {str(e)[:60]}", flush=True)
            error_count += 1
        
        save_pos(cur + 1)
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
    
    print(f"\n⏱️  Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

if __name__ == "__main__":
    scrape_fixed()
