#!/usr/bin/env python3
import subprocess
import sys
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

RESUME = Path("parallel_resume.txt")
MIN = 677500
MAX = 1000000
WORKERS = 50  # Reduced from 100 to ensure reliable saves

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
    """Read actual year from DOCKET (earliest event), not metadata"""
    try:
        matches = list(Path(f"out/{yr}").glob(f"{yr}-{case}_*.json"))
        if not matches:
            return yr
        with open(matches[0]) as f:
            data = json.load(f)
            # Check summary for earliest event date
            summary = data.get('summary', {}).get('fields', {})
            
            # Look for date patterns like 10/17/2025, 08/19/2025, etc
            for key in summary.keys():
                if '/' in key and '202' in key:
                    try:
                        event_year = int(key.split('/')[-1])
                        if 2020 <= event_year <= 2030:
                            return event_year
                    except:
                        pass
            
            # Fallback to metadata
            return data.get('metadata', {}).get('year', yr)
    except:
        return yr

def scrape(case):
    yr = 2023 if case <= 750000 else (2024 if case <= 999999 else 2025)
    try:
        r = subprocess.run(
            ["python3", "main.py", "scrape", "--year", str(yr), "--start", str(case), "--limit", "1", "--direction", "up"],
            capture_output=True,
            timeout=120
        )
        if r.returncode == 0:
            actual_yr = get_year_from_file(case, yr)
            return (case, True, actual_yr)
        else:
            return (case, False, yr)
    except:
        return (case, False, yr)

start = get_pos()
cur = start
tot = 0
current_year = 2023

print(f"\n{'='*70}\n🚀 OPTIMIZED CONTINUOUS SCRAPER (50 WORKERS)\n{'='*70}")
print(f"Start: {start}")
print(f"Target: {MAX}")
print(f"Workers: {WORKERS}")
print(f"{'='*70}\n")

with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    batch = 0
    futures = {}
    
    while cur <= MAX:
        b = []
        for i in range(WORKERS):
            if cur > MAX:
                break
            f = ex.submit(scrape, cur)
            futures[f] = cur
            b.append(cur)
            cur += 1
        
        batch += 1
        print(f"[Batch {batch}] Cases {min(b)}-{max(b)}")
        
        done = 0
        for f in as_completed(futures):
            case, ok, yr = f.result()
            tot += 1
            done += 1
            if done % 5 == 0:
                status = '✓' if ok else '⊝'
                print(f"  [{done:2d}/{len(b)}] Case {case} ({yr}) {status}")
            
            # Track year changes
            if yr != current_year:
                print(f"\n*** YEAR CHANGED: {current_year} → {yr} ***\n")
                current_year = yr
            
            save_pos(case + 1)
            del futures[f]
        
        print(f"[Batch {batch}] ✓ Done | Total Processed: {tot}\n")

print(f"\n{'='*70}")
print(f"✓ DOWNLOAD SESSION COMPLETE")
print(f"Cases Downloaded: {tot}")
print(f"Final Position: {start + tot}")
print(f"{'='*70}\n")
