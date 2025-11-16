#!/usr/bin/env python3
import subprocess
import sys
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import time

RESUME = Path("parallel_resume.txt")
MIN = 697227  # Where we left off
MAX = 710000  # Smart target for all 2025 cases
WORKERS = 30  # Safe worker count
CONSECUTIVE_EMPTIES = 0
MAX_CONSECUTIVE_EMPTIES = 5  # Stop if we hit 5 empty rows in a row

def get_pos():
    if RESUME.exists():
        try:
            return max(int(RESUME.read_text().strip()), MIN)
        except:
            pass
    return MIN

def save_pos(n):
    RESUME.write_text(str(n))

def get_year_from_file(case, yr):
    """Read actual year from case file"""
    try:
        matches = list(Path(f"out/{yr}").glob(f"{yr}-{case}_*.json"))
        if not matches:
            return yr
        with open(matches[0]) as f:
            data = json.load(f)
            summary = data.get('summary', {}).get('fields', {})
            
            # Look for date patterns
            for key in summary.keys():
                if '/' in key and '202' in key:
                    try:
                        event_year = int(key.split('/')[-1])
                        if 2020 <= event_year <= 2030:
                            return event_year
                    except:
                        pass
            
            return data.get('metadata', {}).get('year', yr)
    except:
        return yr

def scrape(case):
    """Scrape case - returns (case, success, year, is_empty)"""
    yr = 2023 if case <= 750000 else (2024 if case <= 999999 else 2025)
    try:
        r = subprocess.run(
            ["python3", "main.py", "scrape", "--year", str(yr), "--start", str(case), "--limit", "1", "--direction", "up"],
            capture_output=True,
            timeout=120,
            text=True
        )
        
        # Check if result is empty/404
        if "not found" in r.stdout.lower() or "not found" in r.stderr.lower() or r.returncode != 0:
            return (case, False, yr, True)  # is_empty = True
        
        actual_yr = get_year_from_file(case, yr)
        return (case, True, actual_yr, False)
    except subprocess.TimeoutExpired:
        return (case, False, yr, True)  # Timeout = skip
    except:
        return (case, False, yr, False)

start = get_pos()
cur = start
tot = 0
current_year = 2025
consecutive_empty = 0
last_success = start

print(f"\n{'='*70}\n🚀 SMART SCRAPER - 2025 COMPLETION MODE\n{'='*70}")
print(f"Start: {start}")
print(f"Target: {MAX}")
print(f"Workers: {WORKERS}")
print(f"Safety: Auto-stop after {MAX_CONSECUTIVE_EMPTIES} empty rows")
print(f"{'='*70}\n")

with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    batch = 0
    futures = {}
    
    while cur <= MAX and consecutive_empty < MAX_CONSECUTIVE_EMPTIES:
        b = []
        for i in range(WORKERS):
            if cur > MAX or consecutive_empty >= MAX_CONSECUTIVE_EMPTIES:
                break
            f = ex.submit(scrape, cur)
            futures[f] = cur
            b.append(cur)
            cur += 1
        
        batch += 1
        print(f"[Batch {batch:3d}] Cases {min(b):7d}-{max(b):7d}")
        
        done = 0
        for f in as_completed(futures):
            case, ok, yr, is_empty = f.result()
            tot += 1
            done += 1
            
            if is_empty:
                consecutive_empty += 1
                status = "⊘ (empty)"
            else:
                if ok:
                    consecutive_empty = 0  # Reset on success
                    last_success = case
                    status = "✓"
                else:
                    status = "⊝ (error)"
            
            if done % 5 == 0 or is_empty:
                print(f"  [{done:2d}/{len(b)}] Case {case:7d} ({yr}) {status:12s} | Empty streak: {consecutive_empty}")
            
            if yr != current_year:
                print(f"\n*** YEAR CHANGED: {current_year} → {yr} ***\n")
                current_year = yr
            
            save_pos(case + 1)
            del futures[f]
        
        print(f"[Batch {batch:3d}] ✓ Done | Total: {tot:4d} | Last success: {last_success:7d}\n")

print(f"\n{'='*70}")
print(f"✓ SCRAPING SESSION COMPLETE")
print(f"Cases Processed: {tot}")
print(f"Final Position: {start + tot}")
print(f"Last Successful Case: {last_success}")
if consecutive_empty >= MAX_CONSECUTIVE_EMPTIES:
    print(f"Stopped due to {consecutive_empty} consecutive empty rows (safety stop)")
print(f"{'='*70}\n")
