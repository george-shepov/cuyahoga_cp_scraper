#!/usr/bin/env python3
"""
Smart scraper targeting complete 2025 coverage + backfill
Last known case: CR-25-707148-A (as of today)
"""
import subprocess
import sys
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

RESUME = Path("parallel_resume.txt")
WORKERS = 25  # Conservative to avoid bans
CONSECUTIVE_EMPTIES_LIMIT = 10

def get_pos():
    if RESUME.exists():
        try:
            return int(RESUME.read_text().strip())
        except:
            pass
    return 707149

def save_pos(n):
    RESUME.write_text(str(n))

def get_year_from_file(case, yr):
    """Read actual year from case file"""
    try:
        matches = list(Path(f"out/{yr}").glob(f"{yr}-{case}_*.json"))
        if matches:
            with open(matches[0]) as f:
                data = json.load(f)
                return data.get('metadata', {}).get('year', yr)
    except:
        pass
    return yr

def scrape(case):
    """Scrape case - returns (case, success, year, is_empty)"""
    yr = 2025 if case >= 700000 else 2024
    try:
        r = subprocess.run(
            ["python3", "main.py", "scrape", "--year", str(yr), "--start", str(case), "--limit", "1", "--direction", "up"],
            capture_output=True,
            timeout=120,
            text=True
        )
        
        # Check for empty/not found
        if r.returncode != 0 or "not found" in r.stdout.lower() or "not found" in r.stderr.lower():
            return (case, False, yr, True)
        
        actual_yr = get_year_from_file(case, yr)
        return (case, True, actual_yr, False)
    except:
        return (case, False, yr, True)

def scrape_range(start, end, description):
    """Scrape a range of cases"""
    print(f"\n{'='*70}")
    print(f"PHASE: {description}")
    print(f"Range: {start} - {end}")
    print(f"Workers: {WORKERS}")
    print(f"{'='*70}\n")
    
    cur = start
    tot = 0
    consecutive_empty = 0
    last_success = start
    batch = 0
    
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        while cur <= end and consecutive_empty < CONSECUTIVE_EMPTIES_LIMIT:
            b = []
            futures = {}
            
            for i in range(WORKERS):
                if cur > end or consecutive_empty >= CONSECUTIVE_EMPTIES_LIMIT:
                    break
                f = ex.submit(scrape, cur)
                futures[f] = cur
                b.append(cur)
                cur += 1
            
            if not b:
                break
            
            batch += 1
            print(f"[Batch {batch:3d}] Cases {min(b):7d}-{max(b):7d}")
            
            done = 0
            for f in as_completed(futures):
                case, ok, yr, is_empty = f.result()
                tot += 1
                done += 1
                
                if is_empty:
                    consecutive_empty += 1
                    status = "⊘ EMPTY"
                else:
                    consecutive_empty = 0
                    last_success = case
                    status = "✓ SAVED"
                
                if done % 5 == 0 or is_empty:
                    print(f"  [{done:2d}/{len(b)}] Case {case:7d} {status}")
                
                save_pos(case + 1)
                del futures[f]
            
            print(f"[Batch {batch}] Done | Total this phase: {tot} | Streak: {consecutive_empty}\n")
    
    print(f"Phase complete: {tot} cases | Last success: {last_success}\n")
    return tot, last_success

# PHASE 1: Get remaining November 2025 (known range)
print(f"\n🚀 SMART SCRAPER - COMPLETE 2025 COLLECTION\n")
print(f"Last known case today: CR-25-707148-A\n")

phase1_tot, phase1_last = scrape_range(707149, 707250, "November 2025 - Complete to end of month")

# PHASE 2: Check October (we already have many but may have gaps)
print(f"\nChecking for October 2025 gaps...")
phase2_tot, phase2_last = scrape_range(706400, 706450, "October 2025 - Gap fill")

# PHASE 3: Get September 2025
phase3_tot, phase3_last = scrape_range(705000, 706400, "September 2025 - Full month")

print(f"\n{'='*70}")
print(f"SUMMARY")
print(f"{'='*70}")
print(f"Phase 1 (Nov 2025):       {phase1_tot:5d} cases | Last: {phase1_last}")
print(f"Phase 2 (Oct backfill):    {phase2_tot:5d} cases | Last: {phase2_last}")
print(f"Phase 3 (Sep 2025):        {phase3_tot:5d} cases | Last: {phase3_last}")
print(f"TOTAL THIS SESSION:        {phase1_tot + phase2_tot + phase3_tot:5d} cases")
print(f"{'='*70}\n")
